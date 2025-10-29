// Live NFL integration for PHI @ NYG game
// Resolves event ID via ESPN scoreboard, waits until kickoff (8:15 PM ET), then polls summary.
(function(){
  // Respect global live fetch flag so we don't hit ESPN endpoints during downtime
  if (typeof window !== 'undefined' && window.LIVE_FETCH_ENABLED === false) {
    console.log('[NFL][LIVE] Skipping NFL live integration (LIVE_FETCH_ENABLED=false)');
    return;
  }
  const KICKOFF_ET = '20:15'; // 24h HH:MM Eastern
  const POLL_INTERVAL_ACTIVE = 20000; // 20s in-game
  const POLL_INTERVAL_IDLE = 60000;  // 1m pre-game retry
  let eventId = null;
  let active = false;
  let kickoffReached = false;
  const chartWrapper = document.getElementById('chartWrapper');
  if(chartWrapper){ chartWrapper.style.display='none'; }

  function easternNowStr(){
    try {
      const fmt = new Intl.DateTimeFormat('en-US',{ timeZone:'America/New_York', hour:'2-digit', minute:'2-digit', hour12:false });
      const parts = fmt.formatToParts(new Date());
      const hh = parts.find(p=>p.type==='hour').value;
      const mm = parts.find(p=>p.type==='minute').value;
      return `${hh}:${mm}`;
    } catch(e){
      // Fallback to local (may be off if not ET)
      const d=new Date();
      return d.toTimeString().slice(0,5);
    }
  }

  function todayScoreboardDate(){
    const est = new Date();
    // Use ET midnight boundaries by constructing date parts with ET
    try {
      const fmt = new Intl.DateTimeFormat('en-US',{ timeZone:'America/New_York', year:'numeric', month:'2-digit', day:'2-digit'});
      const parts = fmt.formatToParts(est);
      const y = parts.find(p=>p.type==='year').value;
      const m = parts.find(p=>p.type==='month').value;
      const d = parts.find(p=>p.type==='day').value;
      return `${y}${m}${d}`;
    } catch(e){
      return est.toISOString().slice(0,10).replace(/-/g,'');
    }
  }

  async function resolveEvent(){
    const SCOREBOARD_DATE = todayScoreboardDate();
    const url = `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=${SCOREBOARD_DATE}`;
    const data = await fetch(url).then(r=>r.json());
    const events = data.events || [];
    const target = events.find(e => (e.shortName||'').toUpperCase().includes('PHI') && (e.shortName||'').toUpperCase().includes('NYG')) ||
                   events.find(e => {
                      const comps = e.competitions?.[0]?.competitors||[];
                      const abbrs = comps.map(c=> c.team?.abbreviation);
                      return abbrs.includes('PHI') && abbrs.includes('NYG');
                   });
    if(target){ eventId = target.id; console.log('[NFL][LIVE] eventId resolved', eventId); }
  }

  function ensureScoreboardRow(state){
    const tbl = document.getElementById('gamesTable');
    if(!tbl) return;
    if(!tbl.querySelector('tr.nfl-live')){
      const tr = document.createElement('tr'); tr.className='nfl-live';
      // Current scoreboard has 3 columns (Game | Score / Status | Spread). We add a row with a sticky label plus one cell spanning the remaining two.
      tr.innerHTML = '<th style="position:sticky;left:0;background:#142028;">NFL</th><td colspan="2" class="nfl-cell" style="white-space:nowrap;">Scheduled 8:15pm</td>';
      tbl.appendChild(tr);
    }
    if(state){
      const cell = tbl.querySelector('tr.nfl-live .nfl-cell');
      if(!cell) return;
      const home = state.teams.find(t=>t.homeAway==='home');
      const away = state.teams.find(t=>t.homeAway==='away');
      const clock = state.status === 'STATUS_FINAL' ? 'FINAL' : `${state.clock||''} Q${state.period||''}`.trim();
      cell.textContent = `${away?.abbr||'AWY'} ${away?.score??''} @ ${home?.abbr||'HOME'} ${home?.score??''}  (${clock})`;
    }
  }

  async function poll(){
    if(!eventId){ await resolveEvent(); }
    const nowStr = easternNowStr();
    if(nowStr >= KICKOFF_ET){ kickoffReached = true; }

    if(!kickoffReached){
      // Always show Scheduled placeholder pre-kickoff
      const tbl = document.getElementById('gamesTable');
      if(tbl){
        let row = tbl.querySelector('tr.nfl-live');
        if(!row){ ensureScoreboardRow(); row = tbl.querySelector('tr.nfl-live'); }
        const cell = row && row.querySelector('.nfl-cell');
        if(cell && cell.textContent !== 'Scheduled 8:15pm'){ cell.textContent = 'Scheduled 8:15pm'; }
      }
      setTimeout(poll, POLL_INTERVAL_IDLE);
      return;
    }
    if(chartWrapper && !active){ chartWrapper.style.display='block'; active = true; }
    if(!eventId){ setTimeout(poll, POLL_INTERVAL_IDLE); return; }
    try {
      const sum = await fetch(`https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=${eventId}`).then(r=>r.json());
      const comp = sum.header?.competitions?.[0];
      const status = comp?.status?.type?.name;
      const clock = comp?.status?.displayClock;
      const period = comp?.status?.period;
      const teams = (comp?.competitors||[]).map(c=> ({
        homeAway: c.homeAway,
        abbr: c.team?.abbreviation,
        score: parseInt(c.score||'0',10)
      }));
      const state = { status, clock, period, teams };
      ensureScoreboardRow(state);
      if(status !== 'STATUS_FINAL'){
        setTimeout(poll, POLL_INTERVAL_ACTIVE);
      } else {
        console.log('[NFL][LIVE] Final captured');
      }
    } catch(e){
      console.warn('[NFL][LIVE] poll error', e); setTimeout(poll, POLL_INTERVAL_IDLE);
    }
  }

  poll();
})();
