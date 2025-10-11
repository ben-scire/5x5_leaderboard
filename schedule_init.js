// Dynamic schedule bootstrap.
// Loads schedule from backend and maps into legacy global variables expected by leaderboard.js
// Must be loaded BEFORE leaderboard.js.

(async function loadScheduleAndInit(){
  if(typeof window!=='undefined' && window.LIVE_FETCH_ENABLED===false){
    console.log('[ScheduleInit] LIVE_FETCH_ENABLED=false; skipping schedule/picks fetch.');
    return;
  }
  try {
    const resp = await fetch('/api/schedule');
    if(!resp.ok){ console.warn('[ScheduleInit] Failed schedule fetch', resp.status); return; }
    const payload = await resp.json();
    const rawDays = payload.days || {};
    // Normalize incoming day keys (e.g., Friday, FRIDAY -> Fri) for robustness.
    const days = {};
    const mapDay = (k) => {
      if(!k) return k;
      const l = k.toLowerCase();
  if(l.startsWith('thu')) return 'Thu';
      if(l.startsWith('fri')) return 'Fri';
      if(l.startsWith('sat')) return 'Sat';
      if(l.startsWith('sun')) return 'Sun';
      if(l.startsWith('mon')) return 'Mon';
      return k; // leave unknown keys unchanged
    };
    Object.keys(rawDays).forEach(k=>{
      const mk = mapDay(k);
      // Prefer explicit canonical key; if duplicate appears, last wins (CSV order)
      days[mk] = rawDays[k];
    });
    // Ensure global containers exist (from config.js)
  // NOTE: Standardize on 'Thu' (previous code sometimes used 'Thurs'). Provide backward compat mapping.
  window.picksLabels = window.picksLabels || { Thu:[], Fri:[], Sat:[], Sun:[], Mon:[] };
  window.userPicks = window.userPicks || { Thu:{}, Fri:{}, Sat:{}, Sun:{}, Mon:{} };
  window.coveredPicks = window.coveredPicks || { Thu:[], Fri:[], Sat:[], Sun:[], Mon:[] };
  if(window.picksLabels.Thurs && !window.picksLabels.Thu){ window.picksLabels.Thu = window.picksLabels.Thurs; }
  if(window.userPicks.Thurs && !window.userPicks.Thu){ window.userPicks.Thu = window.userPicks.Thurs; }
  if(window.coveredPicks.Thurs && !window.coveredPicks.Thu){ window.coveredPicks.Thu = window.coveredPicks.Thurs; }

    function applyDay(dayKey){
      const def = days[dayKey]; if(!def) return;
      const games = (def.games||[]).map(g=>({
        eventId: g.eventId,
        away: g.away, awayAbbr: g.awayAbbr,
        home: g.home, homeAbbr: g.homeAbbr,
        lineHome: g.lineHome,
        total: g.total,
        start: g.start || g.startTime || ''
      }));
      const picks = (def.picks||[]).map(p=> p.label);
      picksLabels[dayKey] = picks;

      // Helper to mutate existing const-declared arrays (defined in config.js) so references elsewhere stay valid.
      function assignDayArrays(arrNameBase, gamesArr){
        const gamesVar = window[arrNameBase+"Games"]; // e.g., fridayGames
        const statesVar = window[arrNameBase+"States"]; // e.g., fridayStates
        const timesName = arrNameBase+"StartTimes";
        const timesVar = window[timesName];
        // Mutate games array
        if(Array.isArray(gamesVar)){
          gamesVar.splice(0, gamesVar.length, ...gamesArr);
        } else {
          window[arrNameBase+"Games"] = gamesArr; // fallback if not pre-declared
        }
        const newStates = gamesArr.map(g=>({ status:'STATUS_SCHEDULED', score:'0-0', home:0, away:0, period:0, clock:'', startTimeStr:g.start || '', meta:{ home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} } }));
        if(Array.isArray(statesVar)){
          statesVar.splice(0, statesVar.length, ...newStates);
        } else {
          window[arrNameBase+"States"] = newStates;
        }
        const newTimes = gamesArr.map(g=> g.start || '');
        if(Array.isArray(timesVar)){
          timesVar.splice(0, timesVar.length, ...newTimes);
        } else {
          window[timesName] = newTimes;
        }
      }

      if(dayKey==='Fri') assignDayArrays('friday', games);
      else if(dayKey==='Sat') assignDayArrays('saturday', games);
      else if(dayKey==='Sun') assignDayArrays('sunday', games);
      else if(dayKey==='Mon') assignDayArrays('monday', games);
      else if(dayKey==='Thu'){ /* Thursday already historical; keep existing config if present */ }
    }

  ['Thu','Fri','Sat','Sun','Mon'].forEach(applyDay);

    // If Friday picks labels came through but fridayGames ended empty (unexpected), rebuild from FRIDAY_SCHEDULE snapshot in payload.
    if((!Array.isArray(window.fridayGames) || !window.fridayGames.length) && days['Fri'] && Array.isArray(days['Fri'].games)){
      window.fridayGames = (days['Fri'].games||[]).map(g=>({
        eventId:g.eventId, away:g.away, awayAbbr:g.awayAbbr, home:g.home, homeAbbr:g.homeAbbr, lineHome:g.lineHome, total:g.total
      }));
      window.fridayStates = window.fridayGames.map(g=>({ status:'STATUS_SCHEDULED', score:'0-0', home:0, away:0, period:0, clock:'', startTimeStr:g.start||'', meta:{ home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} } }));
      window.fridayStartTimes = window.fridayGames.map(g=> g.start || '');
    }

    // Pre-create covered arrays for new days if not set
    ['Fri','Sat','Sun','Mon'].forEach(d=>{ if(!Array.isArray(coveredPicks[d])) coveredPicks[d] = Array((picksLabels[d]||[]).length).fill(null); });

    // Fetch public picks for each active day (except Thurs locked) to hydrate scoring early
    if(typeof window==='undefined' || window.LIVE_FETCH_ENABLED!==false){
      await Promise.all(['Fri','Sat','Sun','Mon'].map(async day=>{
      if(!(picksLabels[day]||[]).length) return;
      try {
        const r = await fetch('/api/picks/public?day='+day);
        if(!r.ok) return;
        const j = await r.json();
        const entries = (j && j.entries) || {};
        Object.keys(entries).forEach(email=>{
          const arr = entries[email].picks || [];
          // pad/trim to length
            const needed = picksLabels[day].length;
            let adj = arr.slice(0, needed);
            while(adj.length < needed) adj.push('');
            userPicks[day][email] = adj;
        });
      } catch(e){ console.warn('[ScheduleInit] public picks load failed', day, e); }
      }));
    }

    console.log('[ScheduleInit] Loaded schedule version', payload.version, 'days:', Object.keys(days));
    // Trigger scoreboard refresh now that schedule is ready
    if(typeof updateScoreboard==='function') try { updateScoreboard(); } catch(_e){}
  } catch(err){ console.warn('[ScheduleInit] Fatal error', err); }
})();
