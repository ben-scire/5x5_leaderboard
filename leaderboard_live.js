// Dynamic live leaderboard + picks rendering using new unified backend APIs.
// Non-invasive: leaves existing legacy static arrays untouched; if backend available,
// replaces table/chart content. Falls back silently if API unreachable.

(function(){
  const LB_API = '/api/leaderboard';
  const SCHED_API = '/api/schedule';
  const PICKS_API = '/api/picks/get'; // requires auth token for user picks (we only need public aggregated picks display?)
  // For public leaderboard we only need /api/leaderboard plus schedule to show pick definitions & results.

  let schedule = null; // loaded schedule
  let leaderboard = null; // last leaderboard payload

  function $(id){ return document.getElementById(id); }

  async function fetchJSON(url){
    try {
      const res = await fetch(url, { cache:'no-store' });
      if(!res.ok) throw new Error(res.status+' '+res.statusText);
      return await res.json();
    } catch(e){
      console.warn('[live] fetch failed', url, e); return null;
    }
  }

  function buildDayToggle(days){
    const bar = $('dayToggleBar'); if(!bar) return;
    if(bar.dataset.enhanced) return; // run once
    bar.dataset.enhanced='1';
    const ordered = Object.keys(days).sort((a,b)=> days[a].order - days[b].order);
    ordered.forEach(d=>{
      const btn = document.createElement('button');
      btn.textContent = d;
      btn.className = 'day-btn';
      btn.addEventListener('click', ()=>{
        currentDay = d; // reuse global consumed by legacy code
        renderGamesTable();
        renderLeaderboardChart();
      });
      bar.appendChild(btn);
    });
  }

  function normalizeResult(res){
    if(!res) return '';
    const u = res.toUpperCase();
    if(['OVER','UNDER','YES','NO','PUSH'].includes(u)) return u;
    return res; // team abbr or name
  }

  function renderGamesTable(){
    const tbl = $('gamesTable'); if(!tbl || !schedule) return;
    const dayDef = schedule.days[currentDay];
    if(!dayDef){ tbl.innerHTML='<tr><td style="padding:8px;color:#888;">No picks for '+currentDay+'</td></tr>'; return; }
    const picks = dayDef.picks || [];
    const rows = [];
    rows.push('<tr><th>#</th><th>Definition</th><th>Result / Time</th></tr>');
    picks.forEach((p,i)=>{
      const type = p.type; // SPREAD | TOTAL | PROP
      let label='';
      if(type === 'SPREAD'){
        // Home-based line: negative => home favored
        const ln = p.lineHome;
        const disp = ln === 0 ? 'PK' : (ln>0? '+'+ln : ln);
        label = `${p.awayAbbr || p.away} @ ${p.homeAbbr || p.home} ${disp}`;
      } else if(type === 'TOTAL'){
        label = `O/U ${p.total}`;
      } else if(type === 'PROP'){
        label = p.propLabel || 'Prop';
      }
      const result = normalizeResult(p.result);
      let timeDisp = '';
      if(!result){
        // Prefer explicit startTimeStr (already normalized human string) else parse startTime
        if(p.startTimeStr){ timeDisp = p.startTimeStr; }
        else if(p.startTime){
          try { const dt = new Date(p.startTime); if(!isNaN(dt.getTime())){ const hrs = dt.getHours(); const mins = dt.getMinutes();
            const h12 = ((hrs+11)%12)+1; const ampm = hrs>=12?'PM':'AM'; const mm = mins.toString().padStart(2,'0'); timeDisp = h12+':'+mm+' '+ampm; } } catch(_){ }
        }
        if(!timeDisp) timeDisp='TBD';
      }
      const cellContent = result ? result : `<span class="sched-time">${timeDisp}</span>`;
      rows.push(`<tr><td>${i+1}</td><td>${label}</td><td class="res ${result? 'has-res':'pending'}">${cellContent}</td></tr>`);
    });
    tbl.innerHTML = rows.join('');
  }

  function renderLeaderboardChart(){
    const tbl = $('leaderboardTable'); if(!tbl) return;
    if(!leaderboard){ tbl.innerHTML = '<tr><td style="padding:8px;color:#888;">Loading leaderboard...</td></tr>'; return; }
    const entries = leaderboard.entries || [];
    if(!entries.length){ tbl.innerHTML = '<tr><td style="padding:8px;color:#888;">No graded picks yet.</td></tr>'; return; }

    // --- Sync emails to legacy global users array (for chart + picks table) ---
    try {
      if(Array.isArray(window.users)){
        const existingSet = new Set(window.users.map(u=>u.username));
        let added=false;
        entries.forEach(e=>{
          if(!existingSet.has(e.email)){
            window.users.push({ username:e.email, thurs:0,fri:0,sat:0,sun:0,mon:0,total:0 });
            existingSet.add(e.email); added=true;
          }
        });
        if(added){
          // Re-render legacy components if present
          if(typeof window.updateLeaderboard==='function') { window.updateLeaderboard(); }
          if(typeof window.renderPicksTable==='function') { window.renderPicksTable(window.currentDay||'Thurs'); }
        }
      }
    } catch(syncErr){ console.warn('[live] user sync failed', syncErr); }

    const dayOrder = leaderboard.dayOrder || [];
    const dayHead = dayOrder.map(d=>`<th>${d}</th>`).join('');
    const header = `<tr><th>Rank</th><th>Player</th>${dayHead}<th>Total</th><th>Ans</th><th>Tot</th></tr>`;
    const body = entries.map((e,i)=>{
      const email = e.email;
      const nick = (window.nicknameMap && window.nicknameMap[email]) || (email.split('@')[0]);
      const perDayCells = dayOrder.map(d=>{
        const st = (e.perDay && e.perDay[d]) || {score:0,answered:0};
        // Show score (answered) for clarity
        return `<td>${st.score}<span class="sub">/${st.answered||0}</span></td>`;
      }).join('');
      return `<tr><td>${i+1}</td><td>${nick}</td>${perDayCells}<td>${e.score}</td><td>${e.answered}</td><td>${leaderboard.totalPossible}</td></tr>`;
    }).join('');
    tbl.innerHTML = header + body;
  }

  async function refresh(){
    if(!schedule){ schedule = await fetchJSON(SCHED_API); if(schedule && schedule.ok){ schedule = schedule.schedule || schedule; buildDayToggle(schedule.days||{}); renderGamesTable(); } }
    leaderboard = await fetchJSON(LB_API) || leaderboard;
    renderLeaderboardChart();
  }

  // Kick off periodic refresh only when live fetching is enabled
  if(typeof window==='undefined' || window.LIVE_FETCH_ENABLED!==false){
    setInterval(refresh, 20000); // 20s
    refresh();
  } else {
    console.log('[live] LIVE_FETCH_ENABLED=false; live polling disabled.');
  }

  // Optional admin submissions monitor (adds a small fetch link if user is admin after they manually set a token in localStorage)
  (function(){
    const linkId='adminSubmissionsLink';
    if(document.getElementById(linkId)) return;
    const nav = document.querySelector('.site-header .header-inner');
    if(!nav) return;
    const a=document.createElement('a'); a.id=linkId; a.textContent='Submissions JSON'; a.style.fontSize='11px'; a.style.marginLeft='12px'; a.href='#';
    a.addEventListener('click', async (e)=>{
      e.preventDefault();
      const token = localStorage.getItem('authToken');
      if(!token){ alert('Store admin token in localStorage.authToken first (login on picks page).'); return; }
      try {
        const r = await fetch('/api/admin/submissions',{ headers:{Authorization:'Bearer '+token} });
        const j = await r.json();
        console.log('[Admin submissions]', j);
        alert(j.ok? 'Submissions data logged to console.' : ('Error: '+j.error));
      } catch(err){ alert('Fetch error'); }
    });
    nav.appendChild(a);
  })();
})();
