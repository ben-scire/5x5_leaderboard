// Dynamic schedule bootstrap.
// Loads schedule from backend and maps into legacy global variables expected by leaderboard.js
// Must be loaded BEFORE leaderboard.js.

(async function loadScheduleAndInit(){
  try {
    const resp = await fetch('/api/schedule');
    if(!resp.ok){ console.warn('[ScheduleInit] Failed schedule fetch', resp.status); return; }
    const payload = await resp.json();
    const days = payload.days || {};
    // Ensure global containers exist (from config.js)
    window.picksLabels = window.picksLabels || { Thurs:[], Fri:[], Sat:[], Sun:[], Mon:[] };
    window.userPicks = window.userPicks || { Thurs:{}, Fri:{}, Sat:{}, Sun:{}, Mon:{} };
    window.coveredPicks = window.coveredPicks || { Thurs:[], Fri:[], Sat:[], Sun:[], Mon:[] };

    function applyDay(dayKey){
      const def = days[dayKey]; if(!def) return;
      const games = (def.games||[]).map(g=>({
        eventId: g.eventId,
        away: g.away, awayAbbr: g.awayAbbr,
        home: g.home, homeAbbr: g.homeAbbr,
        lineHome: g.lineHome,
        total: g.total
      }));
      const picks = (def.picks||[]).map(p=> p.label);
      picksLabels[dayKey] = picks;
  if(dayKey==='Fri'){ window.fridayGames = games; window.fridayStates = games.map((g,i)=>({ status:'STATUS_SCHEDULED', score:'0-0', home:0, away:0, period:0, clock:'', startTimeStr:g.start || '', meta:{ home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} } })); window.fridayStartTimes = games.map(g=> g.start || ''); }
  else if(dayKey==='Sat'){ window.saturdayGames = games; window.saturdayStates = games.map((g,i)=>({ status:'STATUS_SCHEDULED', score:'0-0', home:0, away:0, period:0, clock:'', startTimeStr:g.start || '', meta:{ home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} } })); window.saturdayStartTimes = games.map(g=> g.start || ''); }
      else if(dayKey==='Sun'){ window.sundayGames = games; window.sundayStates = games.map((g,i)=>({ status:'STATUS_SCHEDULED', score:'0-0', home:0, away:0, period:0, clock:'', startTimeStr:g.start || '', meta:{ home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} } })); window.sundayStartTimes = games.map(g=> g.start || ''); }
      else if(dayKey==='Mon'){ window.mondayGames = games; window.mondayStates = games.map((g,i)=>({ status:'STATUS_SCHEDULED', score:'0-0', home:0, away:0, period:0, clock:'', startTimeStr:g.start || '', meta:{ home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} } })); window.mondayStartTimes = games.map(g=> g.start || ''); }
      else if(dayKey==='Thurs'){ /* Thursday already historical; keep existing config if present */ }
    }

    ['Thurs','Fri','Sat','Sun','Mon'].forEach(applyDay);

    // Pre-create covered arrays for new days if not set
    ['Fri','Sat','Sun','Mon'].forEach(d=>{ if(!Array.isArray(coveredPicks[d])) coveredPicks[d] = Array((picksLabels[d]||[]).length).fill(null); });

    // Fetch public picks for each active day (except Thurs locked) to hydrate scoring early
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

    console.log('[ScheduleInit] Loaded schedule version', payload.version);
  } catch(err){ console.warn('[ScheduleInit] Fatal error', err); }
})();
