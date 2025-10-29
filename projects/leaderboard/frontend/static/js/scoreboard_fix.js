// Fallback patch: ensure Saturday games populate scoreboard even if initial schedule hydration races or fails.
// Runs after schedule_init.js. Safe to include repeatedly.
(function(){
  const MAX_ATTEMPTS = 5;
  let attempts = 0;
  async function ensureSaturdaySchedule(){
    try {
      if(Array.isArray(window.saturdayGames) && window.saturdayGames.length === 6) {
        if(attempts===0) console.log('[ScoreboardFix] Saturday games already present (', window.saturdayGames.map(g=>g.eventId).join(', '), ').');
        return true;
      }
      attempts++;
      console.log('[ScoreboardFix] Saturday games missing (len='+(window.saturdayGames?window.saturdayGames.length:'n/a')+') attempt', attempts, '— refetching /api/schedule');
      const r = await fetch('/api/schedule?nocache=' + Date.now(), { cache:'no-store' });
      if(!r.ok){ console.warn('[ScoreboardFix] schedule fetch failed', r.status); return false; }
      const j = await r.json();
      const sat = j && j.days && (j.days.Sat || j.days.SAT || j.days.sat);
      if(sat && Array.isArray(sat.games) && sat.games.length){
        // Mutate existing arrays so other references stay valid
        if(!Array.isArray(window.saturdayGames)) window.saturdayGames = [];
        window.saturdayGames.splice(0, window.saturdayGames.length, ...sat.games.map(g=>({
          eventId:g.eventId, away:g.away, awayAbbr:g.awayAbbr, home:g.home, homeAbbr:g.homeAbbr, lineHome:g.lineHome, total:g.total, start:g.start
        })));
        if(!Array.isArray(window.saturdayStates)) window.saturdayStates = [];
        const newStates = window.saturdayGames.map(g=>({ status:'STATUS_SCHEDULED', score:'0-0', home:0, away:0, period:0, clock:'', startTimeStr:g.start||'', meta:{ home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} } }));
        window.saturdayStates.splice(0, window.saturdayStates.length, ...newStates);
        if(!Array.isArray(window.saturdayStartTimes)) window.saturdayStartTimes = [];
        window.saturdayStartTimes.splice(0, window.saturdayStartTimes.length, ...window.saturdayGames.map(g=> g.start||''));
        console.log('[ScoreboardFix] Rehydrated Saturday games from schedule API. Count=', window.saturdayGames.length);
        if(typeof updateScoreboard==='function') try { updateScoreboard(); } catch(e){}
        return true;
      }
    } catch(err){ console.warn('[ScoreboardFix] error', err); }
    return false;
  }

  function kick(){
    ensureSaturdaySchedule().then(ok=>{
      if(!ok && attempts < MAX_ATTEMPTS){
        setTimeout(kick, 1200);
      } else if(!ok) {
        console.warn('[ScoreboardFix] Exhausted attempts; Saturday games still missing.');
      }
    });
  }
  // Delay start slightly to allow primary schedule_init to run first.
  setTimeout(kick, 800);
})();
