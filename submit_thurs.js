(() => {
  const form = document.getElementById('thursForm');
  const statusEl = document.getElementById('statusMsg');
  const submitBtn = document.getElementById('submitBtn');
  const resetBtn = document.getElementById('resetBtn');
  const summaryBox = document.getElementById('summaryBox');
  const sumEmail = document.getElementById('sumEmail');
  const sumList = document.getElementById('sumList');

  function setStatus(msg, ok=false){
    statusEl.textContent = msg || '';
    statusEl.className = 'status ' + (ok? 'ok':'err');
  }

  resetBtn.addEventListener('click', () => {
    form.reset();
    setStatus('');
    summaryBox.style.display='none';
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    setStatus('Submitting...', true);
    submitBtn.disabled = true;
    try {
      const email = document.getElementById('email').value.trim().toLowerCase();
      if(!email){ setStatus('Email required'); submitBtn.disabled=false; return; }
      const spread = (form.querySelector('input[name="spread"]:checked')||{}).value;
      const total = (form.querySelector('input[name="total"]:checked')||{}).value;
      const prop = (form.querySelector('input[name="prop"]:checked')||{}).value;
      if(!spread||!total||!prop){ setStatus('All picks are required.'); submitBtn.disabled=false; return; }
  const payload = { day:'Thu', email, picks:[spread.toUpperCase(), total.toUpperCase(), prop.toUpperCase()] };
      const resp = await fetch('/api/picks/submit_day', {
        method:'POST',
        headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json().catch(()=>({ ok:false, error:'bad_json'}));
      if(!resp.ok || !data.ok){
        const err = data.error || ('HTTP '+resp.status);
        setStatus('Error: ' + err);
        submitBtn.disabled=false;
        return;
      }
      setStatus('Saved!', true);
      sumEmail.textContent = email;
      sumList.innerHTML = '';
      ['Spread','Total','Prop'].forEach((label,i)=>{
        const li=document.createElement('li');
        li.textContent = label+': '+payload.picks[i];
        sumList.appendChild(li);
      });
      summaryBox.style.display='block';
    } catch(err){
      console.error(err);
      setStatus('Unexpected error: ' + err.message);
    } finally {
      submitBtn.disabled=false;
    }
  });
})();