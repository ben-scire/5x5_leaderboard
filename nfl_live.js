// Live NFL integration for PHI @ NYG game
// Resolves event ID via ESPN scoreboard, waits until kickoff (8:15 PM ET), then polls summary.
(function(){
  const KICKOFF_ET = '20:15'; // 24h HH:MM Eastern
  const DATE_ISO = new Date().toISOString().slice(0,10); // current date (assumes same day)
  const SCOREBOARD_DATE = DATE_ISO.replace(/-/g,'');
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

  async function resolveEvent(){
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
      tr.innerHTML = '<th style="position:sticky;left:0;background:#142028;">NFL</th><td colspan="4" class="nfl-cell" style="white-space:nowrap;">Loading PHI @ NYG…</td>';
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
      // Pre-game: show countdown placeholder
      ensureScoreboardRow();
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

  // Kickoff poll cycle
  poll();
})();
