/* Auth + dynamic picks UI logic
   Uses new endpoints: /api/auth/create, /api/auth/login, /api/picks/get, /api/picks/save
   Relies on schedule_init.js having populated window._schedule (days) and pick definitions.
*/
(function(){
  const LS_KEY = 'authToken';
  const state = {
    token: localStorage.getItem(LS_KEY) || null,
    email: null,
    isAdmin: false,
    currentDay: null,
    dayMeta: {}, // day -> { picks:[], locked:[] }
    schedule: null
  };

  function $(id){ return document.getElementById(id); }
  const authStatusEl = $('authStatus');
  const accountInfoEl = $('accountInfo');
  const accountEmailEl = $('accountEmail');
  const dynPanel = $('dynamicPicksPanel');
  const dayBtnsWrap = $('dayPickerButtons');
  const dayPicksFields = $('dayPicksFields');
  const saveStatusEl = $('saveStatus');
  const saveBtn = $('savePicksBtn');
  const dayForm = $('dayPicksForm');

  function setAuthStatus(msg){ authStatusEl.textContent = msg; }
  function setSaveStatus(msg, ok){
    saveStatusEl.textContent = msg || '';
    saveStatusEl.style.color = ok === false ? '#c33' : '#888';
  }

  function bearerHeaders(){
    return state.token ? { 'Authorization': 'Bearer ' + state.token, 'Content-Type': 'application/json' } : { 'Content-Type':'application/json' };
  }

  function refreshScheduleRef(){
    if (window._scheduleDays){
      state.schedule = window._scheduleDays; // { day: { picks: [...], games:[...] } }
    }
  }

  function buildDayButtons(){
    dayBtnsWrap.innerHTML='';
    if(!state.schedule) return;
    Object.keys(state.schedule).forEach(day=>{
      const btn = document.createElement('button');
      btn.type='button';
      btn.textContent = day;
      btn.className = 'day-btn' + (day===state.currentDay?' active':'');
      btn.onclick = ()=> selectDay(day);
      dayBtnsWrap.appendChild(btn);
    });
  }

  function selectDay(day){
    state.currentDay = day;
    buildDayButtons();
    fetchDayPicks(day);
  }

  async function fetchDayPicks(day){
    if(!state.token) return;
    if(typeof window!=='undefined' && window.LIVE_FETCH_ENABLED===false) { setSaveStatus('Live fetching disabled'); return; }
    try{
      const res = await fetch('/api/picks/get?day='+encodeURIComponent(day), { headers: bearerHeaders() });
      const data = await res.json();
      if(!data.ok){
        setSaveStatus('Error loading picks: '+(data.error||res.status), false);return;
      }
      state.dayMeta[day]={ picks: data.picks.slice(), locked: data.locked.slice() };
      renderDayFields(day);
      setSaveStatus('Loaded '+day+' picks');
    }catch(e){ setSaveStatus('Network error loading picks', false); }
  }

  function renderDayFields(day){
    dayPicksFields.innerHTML='';
    const dayDef = state.schedule[day];
    if(!dayDef){ dayPicksFields.innerHTML='<em>No definitions.</em>'; return; }
    const pickDefs = dayDef.picks || [];
    const meta = state.dayMeta[day];
    if(!meta){ return; }
    pickDefs.forEach((pd, i)=>{
      const wrap = document.createElement('div');
      wrap.className='pick-field-row';
      const label = document.createElement('label');
      label.innerHTML = `<span class="pick-label">${pd.label}</span>`;
      let input;
      const locked = meta.locked[i];
      if(pd.type==='TOTAL'){
        input = document.createElement('select');
        ['','OVER','UNDER'].forEach(opt=>{
          const o=document.createElement('option');o.value=opt;o.textContent=opt||'Select';input.appendChild(o);
        });
      } else if(pd.type==='PROP'){
        input = document.createElement('select');
        ['','YES','NO'].forEach(opt=>{
          const o=document.createElement('option');o.value=opt;o.textContent=opt||'Select';input.appendChild(o);
        });
      } else { // SPREAD or generic
        input = document.createElement('input');
        input.type='text';
        input.placeholder='Team / Side';
        input.autocomplete='off';
      }
      input.dataset.index=i;
      input.value = meta.picks[i] || '';
      if(locked){
        input.disabled = true;
        wrap.classList.add('locked');
      }
      input.onchange = ()=>{
        const idx = +input.dataset.index;
        meta.picks[idx] = input.value.toUpperCase();
      };
      label.appendChild(input);
      if(locked){
        const lockSpan=document.createElement('span');
        lockSpan.className='lock-ind';
        lockSpan.textContent='Locked';
        label.appendChild(lockSpan);
      } else {
        const timer = document.createElement('span');
        timer.className='lock-timer';
        timer.dataset.index=i;
        timer.textContent='--m --s';
        label.appendChild(timer);
      }
      wrap.appendChild(label);
      dayPicksFields.appendChild(wrap);
    });
  }

  dayForm.addEventListener('submit', async (e)=>{
    e.preventDefault();
    if(!state.currentDay){ return; }
    const meta = state.dayMeta[state.currentDay];
    if(!meta){ return; }
    setSaveStatus('Saving...');
    try{
      const res = await fetch('/api/picks/save', {
        method:'POST',
        headers: bearerHeaders(),
        body: JSON.stringify({ day: state.currentDay, picks: meta.picks })
      });
      const data = await res.json();
      if(!data.ok){
        if(data.error==='locked_picks'){
          setSaveStatus('Some picks locked ('+data.indices.join(',')+')', false);
        } else setSaveStatus('Save failed: '+data.error, false);
        return;
      }
      setSaveStatus('Saved at '+(new Date()).toLocaleTimeString());
      if(data.locked){
        state.dayMeta[state.currentDay].locked = data.locked.slice();
        renderDayFields(state.currentDay);
      }
    }catch(err){ setSaveStatus('Network error saving picks', false); }
  });

  // Account forms
  const createForm = document.getElementById('createAccountForm');
  const loginForm = document.getElementById('loginForm');
  const logoutBtn = document.getElementById('logoutBtn');

  function showAccount(email,isAdmin){
    createForm.style.display='none';
    loginForm.style.display='none';
    accountInfoEl.style.display='block';
    dynPanel.style.display='block';
    accountEmailEl.textContent=email+(isAdmin?' (Admin)':'');
    setAuthStatus('Signed in');
    refreshScheduleRef();
    buildDayButtons();
    // Default to first day if none selected
    if(!state.currentDay && state.schedule){
      const firstDay = Object.keys(state.schedule)[0];
      if(firstDay){ selectDay(firstDay); }
    }
  }
  function clearAccount(){
    accountInfoEl.style.display='none';
    createForm.style.display='block';
    loginForm.style.display='block';
    dynPanel.style.display='none';
    setAuthStatus('Not signed in');
    state.currentDay=null;
  }

  function handleAuthResponse(data, form){
    const msgEl = form.querySelector('[data-role=msg]');
    if(!data.ok){
      msgEl.textContent = data.error || 'Error';
      msgEl.style.color='#c33';
      return;
    }
    state.token=data.token; localStorage.setItem(LS_KEY, state.token);
    state.email=form.elements.email.value.trim().toLowerCase();
    state.isAdmin=!!data.isAdmin;
    msgEl.textContent='Success';
    msgEl.style.color='#2b7';
    showAccount(state.email,state.isAdmin);
  }

  createForm.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const email = createForm.elements.email.value.trim();
    const password = createForm.elements.password.value;
    const res = await fetch('/api/auth/create', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email, password }) });
    const data = await res.json();
    handleAuthResponse(data, createForm);
  });
  loginForm.addEventListener('submit', async (e)=>{
    e.preventDefault();
    const email = loginForm.elements.email.value.trim();
    const password = loginForm.elements.password.value;
    const res = await fetch('/api/auth/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email, password }) });
    const data = await res.json();
    handleAuthResponse(data, loginForm);
  });
  logoutBtn.addEventListener('click', ()=>{
    state.token=null; localStorage.removeItem(LS_KEY); clearAccount(); setSaveStatus('');
  });

  // Try silent auth with existing token (validate by fetching first day once schedule ready)
  async function attemptTokenReuse(){
    if(!state.token) return;
    if(typeof window!=='undefined' && window.LIVE_FETCH_ENABLED===false) return;
    try {
      const res = await fetch('/api/auth/status', { headers: bearerHeaders() });
      const data = await res.json();
      if(!data.ok){ state.token=null; localStorage.removeItem(LS_KEY); return; }
      state.email = data.email;
      state.isAdmin = !!data.isAdmin;
      showAccount(state.email, state.isAdmin);
    } catch(e){ /* ignore */ }
  }

  // Wait a tick for schedule_init to populate
  setTimeout(()=>{ refreshScheduleRef(); buildDayButtons(); attemptTokenReuse(); }, 400);

  // Countdown polling for pick locks
  async function pollCountdowns(){
    try {
      const res = await fetch('/api/schedule/countdowns');
      const data = await res.json();
      if(!data.ok) return;
      if(!state.currentDay) return;
      const arr = data.countdowns[state.currentDay];
      if(!arr) return;
      const timers = dayPicksFields.querySelectorAll('.lock-timer');
      timers.forEach(el=>{
        const idx = +el.dataset.index;
        const ms = arr[idx];
        if(ms == null){ el.textContent=''; return; }
        if(ms === 0){
            el.textContent='Locked';
            el.classList.add('locked');
            const inp = dayPicksFields.querySelector('[data-index="'+idx+'"]');
            if(inp){ inp.disabled = true; }
            return;
        }
        const sec = Math.floor(ms/1000);
        const m = Math.floor(sec/60);
        const s = sec % 60;
        el.textContent = m+'m '+(s<10?'0':'')+s+'s';
      });
    } catch(e){ /* ignore */ }
  }
  if(typeof window==='undefined' || window.LIVE_FETCH_ENABLED!==false){
    setInterval(pollCountdowns, 15000); // every 15 seconds
    setTimeout(pollCountdowns, 5000);
  }
})();
