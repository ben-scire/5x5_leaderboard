// Dynamic live leaderboard + picks rendering using new unified backend APIs.
(function(){
  const LB_API = '/api/leaderboard';
  const SCHED_API = '/api/schedule';
  let schedule = null; let leaderboard = null; let currentDay = null;
  function $(id){ return document.getElementById(id); }
  async function fetchJSON(url){ try{ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw 0; return await r.json(); }catch(e){ return null; } }
  function firstDay(days){ const keys=Object.keys(days||{}); if(!keys.length) return null; return keys.sort((a,b)=> (days[a].order||0)-(days[b].order||0))[0]; }
  function buildDayToggle(days){ const bar=$('dayToggleBar'); if(!bar||bar.dataset.enhanced) return; bar.dataset.enhanced='1'; const ordered=Object.keys(days).sort((a,b)=> (days[a].order||0)-(days[b].order||0)); if(!currentDay) currentDay = firstDay(days); ordered.forEach(d=>{ const btn=document.createElement('button'); btn.textContent=d; btn.className='day-btn'; if(d===currentDay) btn.classList.add('active'); btn.onclick=()=>{ currentDay=d; [...bar.querySelectorAll('button')].forEach(b=>b.classList.toggle('active', b.textContent===d)); renderGamesTable(); renderLeaderboard(); }; bar.appendChild(btn); }); }
  function renderGamesTable(){ const tbl=$('gamesTable'); if(!tbl||!schedule) return; if(!currentDay){ tbl.innerHTML='<tr><td style="padding:8px;color:#888;">No schedule loaded</td></tr>'; return; } const def=schedule.days[currentDay]; if(!def){ tbl.innerHTML='<tr><td style="padding:8px;color:#888;">No picks</td></tr>'; return; } const rows=['<tr><th>#</th><th>Pick</th><th>Result</th></tr>']; const games=def.games||[]; (def.picks||[]).forEach((p,i)=>{ const game=p.gameIndex!=null?games[p.gameIndex]:null; // use precomputed label from backend for consistency
    const label = p.label || (game? `${game.awayAbbr} @ ${game.homeAbbr}` : 'Pick');
    const res=(p.result||'').toUpperCase();
    rows.push(`<tr><td>${i+1}</td><td>${label}</td><td class="res ${res?'has-res':''}">${res}</td></tr>`); }); tbl.innerHTML=rows.join(''); }
  function renderLeaderboard(){ const tbl=$('leaderboardTable'); if(!tbl){ return;} if(!leaderboard){ tbl.innerHTML='<tr><td style="padding:8px;color:#888;">Loading...</td></tr>'; return;} const entries=leaderboard.entries||[]; if(!entries.length){ tbl.innerHTML='<tr><td style="padding:8px;color:#888;">No data</td></tr>'; return;} const dayOrder=leaderboard.dayOrder||[]; const head=`<tr><th>Rank</th><th>Player</th>${dayOrder.map(d=>`<th>${d}</th>`).join('')}<th>Total</th><th>Ans</th><th>Tot</th></tr>`; const body=entries.map((e,i)=>{ const nick=(window.nicknameMap&&window.nicknameMap[e.email])||e.email.split('@')[0]; const per=dayOrder.map(d=>{ const st=e.perDay&&e.perDay[d]; return `<td>${st? st.score:0}<span class="sub">/${(st&&st.answered)||0}</span></td>`; }).join(''); return `<tr><td>${i+1}</td><td>${nick}</td>${per}<td>${e.score}</td><td>${e.answered}</td><td>${leaderboard.totalPossible}</td></tr>`; }).join(''); tbl.innerHTML=head+body; }
  async function refresh(){ if(!schedule){ const s=await fetchJSON(SCHED_API); if(s&&s.ok){ schedule=s.schedule||s; buildDayToggle(schedule.days||{}); renderGamesTable(); }} const lb=await fetchJSON(LB_API); if(lb&&lb.ok) leaderboard=lb; renderLeaderboard(); }
  setInterval(refresh,20000); refresh();
})();
