// Generic per-day picks submission logic.
// Assumes schedule_init.js already populated picksLabels and userPicks.

(function(){
  const hostId = 'submissionPanel';
  function ensureHost(){
    let el = document.getElementById(hostId);
    if(!el){
      el = document.createElement('div');
      el.id = hostId;
      el.className = 'submission-panel';
      const anchor = document.getElementById('picksGroup') || document.body;
      anchor.parentNode.insertBefore(el, anchor);
    }
    return el;
  }
  function renderForm(day){
    const host = ensureHost();
    const labels = (window.picksLabels && window.picksLabels[day]) || [];
    if(!labels.length){ host.innerHTML = ''; return; }
    host.innerHTML = `
      <div class="submit-card">
        <h3 style="margin-top:0">Submit ${day} Picks</h3>
        <div class="row"><label>Email <input type="email" id="ps-email" required></label></div>
        <div class="row"><label>Phrase <input type="password" id="ps-phrase" required></label></div>
        <div id="ps-picks" class="picks-inputs">${labels.map((l,i)=>`<div class="row"><label>${l}<input data-idx="${i}" type="text" placeholder="Pick ${i+1}"></label></div>`).join('')}</div>
        <div class="row actions"><button id="ps-unlock">Unlock</button><button id="ps-submit" disabled>Submit</button><span id="ps-status" class="status"></span></div>
      </div>`;
    wireEvents(day);
  }
  function normalizePick(raw){ return (raw||'').trim(); }
  async function unlock(day){
    const email = document.getElementById('ps-email').value.trim().toLowerCase();
    const phrase = document.getElementById('ps-phrase').value.trim();
    const status = document.getElementById('ps-status');
    status.textContent = '...';
    try {
      const resp = await fetch('/api/picks/unlock',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email, phrase, day }) });
      const j = await resp.json();
      if(!resp.ok || !j.ok){ status.textContent = j.error || 'Unlock failed'; return; }
      status.textContent = j.submitted ? 'Already submitted (locked)' : 'Unlocked';
      if(Array.isArray(j.picks)){
        j.picks.forEach((v,i)=>{ const inp = document.querySelector(`#ps-picks input[data-idx="${i}"]`); if(inp) inp.value = v; });
        if(j.submitted){ document.getElementById('ps-submit').disabled = true; }
      } else {
        document.getElementById('ps-submit').disabled = false;
      }
    } catch(e){ status.textContent = 'Unlock error'; }
  }
  async function submit(day){
    const email = document.getElementById('ps-email').value.trim().toLowerCase();
    const phrase = document.getElementById('ps-phrase').value.trim();
    const status = document.getElementById('ps-status');
    const labels = (picksLabels[day]||[]);
    const picks = labels.map((_,i)=>{ const inp = document.querySelector(`#ps-picks input[data-idx="${i}"]`); return normalizePick(inp && inp.value); });
    status.textContent = 'Saving...';
    try {
      const resp = await fetch('/api/picks/submit',{ method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ email, phrase, day, picks }) });
      const j = await resp.json();
      if(!resp.ok || !j.ok){ status.textContent = j.error || 'Submit failed'; return; }
      status.textContent = 'Saved';
      document.getElementById('ps-submit').disabled = true;
      // Mirror locally for immediate leaderboard update.
      (window.userPicks[day] = window.userPicks[day] || {})[email] = picks;
      if(typeof recalcPoints==='function'){ recalcPoints(day); recalcTotal(); updateLeaderboard(); if(picksDay===day) renderPicksTable(day); }
    } catch(e){ status.textContent='Submit error'; }
  }
  function wireEvents(day){
    const btnU = document.getElementById('ps-unlock');
    const btnS = document.getElementById('ps-submit');
    if(btnU) btnU.addEventListener('click', ()=> unlock(day));
    if(btnS) btnS.addEventListener('click', ()=> submit(day));
  }
  // Expose day change hook
  window.renderSubmissionForm = renderForm;
  // Initial attempt: wait a beat for schedule load then show current selected picksDay
  document.addEventListener('DOMContentLoaded', ()=> setTimeout(()=>{ if(typeof picksDay!=='undefined') renderForm(picksDay); }, 400));
  // Patch day toggle to re-render form when switching days
  const origToggle = window.__renderDayToggle;
  window.__renderDayToggle = function(){ if(origToggle) origToggle(); if(typeof picksDay!=='undefined') renderForm(picksDay); };
})();
