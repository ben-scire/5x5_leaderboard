// Unified picks submission client for new backend.
(function(){
  const SCHEDULE_URL='/api/schedule';
  const GET_URL='/api/picks/get';
  const SAVE_URL='/api/picks/save';
  const LOGIN_URL='/api/auth/login';
  const CREATE_URL='/api/auth/create';
  let schedule=null, token=null, email=null, userPicks={}, locksByDay={};
  const remaining=[]; // flattened list of remaining pick objects { day, index, def, existing, locked }

  function $(id){ return document.getElementById(id); }
  function setStatus(id,msg,ok){ const el=$(id); if(!el) return; el.textContent=msg||''; el.style.color = ok? '#4caf50':'#f44336'; }
  async function api(url, method='GET', body){
    const opt={ method, headers:{'Content-Type':'application/json'} };
    if(token) opt.headers.Authorization='Bearer '+token;
    if(body) opt.body=JSON.stringify(body);
    const res = await fetch(url,opt); let j=null; try{ j=await res.json(); }catch(_){ }
    if(!res.ok) throw (j&&j.error)||res.statusText; return j; }

  async function login(create){
    const e=$('email').value.trim().toLowerCase(); const p=$('password').value.trim();
    if(!e||!p){ setStatus('authStatus','Email & password required'); return; }
    setStatus('authStatus', create?'Creating...':'Logging in...', true);
    try { const j=await api(create?CREATE_URL:LOGIN_URL,'POST',{email:e,password:p}); token=j.token; email=e; setStatus('authStatus', create?'Created & Logged In':'Logged In', true);
      $('authPanel').style.display='none'; $('picksPanel').style.display='block'; $('userLabel').textContent=email; await loadData(); }
    catch(err){ setStatus('authStatus', err.toString()); }
  }

  function defLabel(p){
    if(!p) return '';
    if(p.type==='SPREAD'){ const ln=p.lineHome; const disp= ln===0?'PK':(ln>0?'+'+ln:ln); return `${p.awayAbbr||p.away} @ ${p.homeAbbr||p.home} ${disp}`; }
    if(p.type==='TOTAL') return `O/U ${p.total}`;
    if(p.type==='PROP') return p.propLabel||'Prop';
    return p.type||'';
  }

  function buildRemaining(){
    remaining.length=0;
    const days = schedule.days || {};
    const ordered = Object.keys(days).sort((a,b)=> days[a].order - days[b].order);
    ordered.forEach(day=>{
      const defs = (days[day].picks)||[];
      const userDay = (userPicks[day] && userPicks[day].picks) || [];
      const locks = locksByDay[day] || [];
      defs.forEach((def,i)=>{
        const locked = !!locks[i];
        const existing = userDay[i] || '';
        // Skip if locked (already past) OR result already set (graded) OR user already has a pick (still allow edit? user request is remaining only) -> we exclude edits.
        if(locked) return;
        if(def.result) return; // already graded/resolved
        if(existing) return; // user already picked, exclude from remaining list
        remaining.push({ day, index:i, def, existing:'' });
      });
    });
  }

  function renderRemaining(){
    const wrap = $('remainingWrap');
    if(!wrap){ return; }
    if(!remaining.length){ wrap.innerHTML='<div style="padding:8px;color:#888;">No remaining picks to enter.</div>'; $('btnSave').disabled=true; return; }
    const rows = remaining.map((r,ri)=>{
      return `<tr><td>${ri+1}</td><td>${r.day}</td><td>${defLabel(r.def)}</td><td>${r.def.type}</td><td><input data-ri="${ri}" type="text" placeholder="Pick" value=""></td></tr>`;
    }).join('');
    wrap.innerHTML = `<table class="picks-edit"><tr><th>#</th><th>Day</th><th>Definition</th><th>Type</th><th>Your Pick</th></tr>${rows}</table>`;
    $('btnSave').disabled=false;
  }

  async function saveAll(){
    setStatus('saveStatus','Saving...', true);
    try {
      // Group inputs by day, reconstruct full pick arrays (keeping existing picks for earlier indices) while filling only new ones.
      const dayBuffers = {}; // day -> array (sized to definitions length)
      remaining.forEach((r,ri)=>{
        const val = (document.querySelector(`input[data-ri="${ri}"]`)||{}).value || '';
        if(!dayBuffers[r.day]){
          const defs = schedule.days[r.day].picks || [];
          const existing = (userPicks[r.day] && userPicks[r.day].picks) || [];
            dayBuffers[r.day] = Array.from({length: defs.length}, (_,i)=> existing[i] || '');
        }
        dayBuffers[r.day][r.index] = val.trim();
      });
      // Save each day sequentially
      for(const [day,picksArr] of Object.entries(dayBuffers)){
        const resp = await api(SAVE_URL,'POST',{ day, picks: picksArr });
        if(!resp.ok) throw resp.error || ('Save failed for '+day);
        userPicks[day] = { picks: picksArr, ts: Date.now() };
        locksByDay[day] = resp.locked || locksByDay[day] || [];
      }
      buildRemaining(); renderRemaining();
      setStatus('saveStatus','Saved', true);
    } catch(e){ setStatus('saveStatus', e.toString()); }
  }

  async function loadData(){
    try {
      const sched = await api(SCHEDULE_URL); schedule = (sched.schedule)||sched;
      const picksResp = await api(GET_URL + '?email=' + encodeURIComponent(email));
      userPicks = picksResp.picks || {}; locksByDay = picksResp.locks || {};
      buildRemaining(); renderRemaining();
    } catch(e){ setStatus('saveStatus','Load failed: '+e); }
  }

  $('btnLogin').addEventListener('click', ()=> login(false));
  $('btnCreate').addEventListener('click', ()=> login(true));
  $('btnSave').addEventListener('click', saveAll);
})();
