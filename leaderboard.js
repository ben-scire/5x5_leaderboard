/* Core logic extracted from leaderboard.html */

// Pre-populate users list with any already-submitted Thursday emails (immediate display even with live disabled)
(function immediateThuSeed(){
  if(typeof fetch==='function'){
    try {
      fetch('/api/picks/status/Thu', { cache:'no-store' })
        .then(r=> r.ok? r.json(): null)
        .then(j=>{
          if(!j || !j.ok || !Array.isArray(j.submitted)|| !window.users) return;
          const existing = new Set(window.users.map(u=>u.username));
          let added=false;
          j.submitted.forEach(em=>{ if(!existing.has(em)){ window.users.push({ username:em, thurs:0,fri:0,sat:0,sun:0,mon:0,total:0 }); added=true; } });
          if(added && typeof window.updateLeaderboard==='function') { window.updateLeaderboard(); }
          if(added && typeof window.renderPicksTable==='function'){ window.renderPicksTable('Thu'); }
        })
        .catch(()=>{});
    } catch(_e) { /* silent */ }
  }
})();

// Static final results for past days (used when those days are complete or when
// dynamic game objects are not present/loaded). This guarantees a scoreboard
// row with actual final scores instead of a blank table.
// NOTE: Thursday NFL: Miami @ Buffalo final 21-31 (BUF wins, MIA covers +11.5, total 52 > 50.5 => Over)
// Static finals only retained for Thursday fallback; Friday will always rely on schedule/live state to avoid 0-0 FINAL artifact.
const finalResults = {
  'Thu': [ { awayAbbr:'PHI', homeAbbr:'NYG', awayScore:0, homeScore:0, lineHome:7.5, total:40.5 } ]
};

// Hydrate Friday picks immediately if public endpoint already has entries (covers issue with users missing on load)
(async function hydrateFridayPicksEarly(){
  try {
    const r = await fetch('/api/picks/public?day=Fri',{cache:'no-store'});
    if(!r.ok) return; const j = await r.json(); const entries = (j&&j.entries)||{};
    Object.keys(entries).forEach(email=>{
      if(!userPicks.Fri[email]){
        const arr = entries[email].picks || [];
        const needed = (picksLabels && picksLabels.Fri && picksLabels.Fri.length) ? picksLabels.Fri.length : (arr.length || 2);
        let adj = arr.slice(0, needed);
        while(adj.length < needed) adj.push('');
        userPicks.Fri[email] = adj;
        // Ensure user object exists for leaderboard
        if(!users.find(u=>u.username===email)){
          users.push({ username:email, thurs:0,fri:0,sat:0,sun:0,mon:0,total:0 });
        }
      } else {
        // Merge in any missing slots if labels expanded later
        const needed = picksLabels.Fri.length;
        if(userPicks.Fri[email].length < needed){
          while(userPicks.Fri[email].length < needed) userPicks.Fri[email].push('');
        }
      }
    });
    if(typeof renderPicksTable==='function') renderPicksTable('Fri');
    if(typeof updateLeaderboard==='function') updateLeaderboard();
  } catch(e){ /* silent */ }
})();

// Early Saturday hydration: ensure all users with Saturday submissions appear immediately
// and at least the first two game columns render on initial load.
(async function hydrateSaturdayPicksEarly(){
  try {
    const r = await fetch('/api/picks/public?day=Sat',{cache:'no-store'});
    if(!r.ok) return; const j = await r.json(); const entries=(j&&j.entries)||{};
    const firstTwoCount = 2; // explicitly show first two games
    Object.keys(entries).forEach(email=>{
      const arr = entries[email].picks || [];
      // Truncate/pad to at least firstTwoCount so table shows two columns even before labels fully hydrate
      let needed = (picksLabels && picksLabels.Sat && picksLabels.Sat.length) ? picksLabels.Sat.length : Math.max(firstTwoCount, arr.length);
      if(needed < firstTwoCount) needed = firstTwoCount;
      let adj = arr.slice(0, needed);
      while(adj.length < needed) adj.push('');
      if(!userPicks.Sat[email]){
        userPicks.Sat[email] = adj;
        if(!users.find(u=>u.username===email)){
          users.push({ username:email, thurs:0,fri:0,sat:0,sun:0,mon:0,total:0 });
        }
      } else {
        if(userPicks.Sat[email].length < needed){
          while(userPicks.Sat[email].length < needed) userPicks.Sat[email].push('');
        }
      }
    });
    // Ensure all known users (from existing users array) have at least placeholder Saturday picks for first two games
    users.forEach(u=>{
      if(!userPicks.Sat[u.username]){
        userPicks.Sat[u.username] = Array(firstTwoCount).fill('');
      } else if(userPicks.Sat[u.username].length < firstTwoCount){
        while(userPicks.Sat[u.username].length < firstTwoCount) userPicks.Sat[u.username].push('');
      }
    });
    if(typeof renderPicksTable==='function') renderPicksTable('Sat');
    if(typeof updateLeaderboard==='function') updateLeaderboard();
  } catch(e){ /* silent */ }
})();

function abbrevUser(u){ return nicknameMap[u.username] || u.username.split('@')[0]; }
// Determine which side is covering given a home-based spread (negative => home favored, positive => away favored)
// Robust spread resolver (home-based line):
// lineHome < 0  => home is favored by abs(lineHome)
// lineHome > 0  => away is favored by lineHome (home is underdog)
// Returns 'HOME' | 'AWAY' | 'PUSH'
function determineCoverSpread(homeScore, awayScore, lineHome){
  if(typeof homeScore!=='number') homeScore = parseFloat(homeScore)||0;
  if(typeof awayScore!=='number') awayScore = parseFloat(awayScore)||0;
  if(typeof lineHome!=='number') lineHome = parseFloat(lineHome)||0;
  const margin = homeScore - awayScore; // positive => home leading
  if(lineHome === 0){
    if(margin>0) return 'HOME';
    if(margin<0) return 'AWAY';
    return 'PUSH';
  }
  if(lineHome < 0){
    // Home favored by abs(lineHome). Need margin > abs(line) to cover.
    const need = Math.abs(lineHome);
    if(margin > need) return 'HOME';
    if(margin < need) return 'AWAY';
    return 'PUSH';
  } else {
    // Away favored by lineHome. Away margin = -margin (awayScore - homeScore)
    const need = lineHome;
    const awayMargin = -margin;
    if(awayMargin > need) return 'AWAY';
    if(awayMargin < need) return 'HOME';
    return 'PUSH';
  }
}
function canonicalTeamName(str){ return !str ? str : str.replace(/^#\d+\s*/,'').trim(); }
// Lightweight NFL abbreviation normalization (handle AZ vs ARI etc.)
function normalizeNFLAbbr(abbr){
  if(!abbr) return abbr;
  const up = abbr.toUpperCase();
  if(up==='AZ') return 'ARI';
  if(up==='JAX') return 'JAX';
  if(up==='NE') return 'NE';
  if(up==='NO') return 'NO';
  if(up==='KC') return 'KC';
  if(up==='GB') return 'GB';
  if(up==='WSH' || up==='WAS' || up==='WASH') return 'WSH';
  return up;
}
// Core pick vs cover comparison (normalization-aware). Added after removal of earlier helper.
function picksMatch(a,b){
  if(a==null || b==null) return false;
  // Direct fast path
  if(a===b) return true;
  const na = _norm(a);
  const nb = _norm(b);
  if(na && nb && na===nb) return true;
  // Abbreviation fallback (e.g., comparing OHIO ST vs Ohio State via table abbrev map)
  const la = lookupAbbr(a);
  const lb = lookupAbbr(b);
  if(la===lb) return true;
  return false;
}
// Normalize existing Saturday covered picks
// NOTE: Week Thursday picks are static & locked (see config.js userPicks['Thu']).
coveredPicks['Sat'] = coveredPicks['Sat'].map(c=> (c && c!=='PUSH') ? canonicalTeamName(c) : c);

// --- Unified normalization / synonym mapping for looser matching (esp. Saturday) ---
// Central place so both quick recalcPoints and detailed pointsForDay stay consistent.
function _norm(raw){
  if(raw==null) return '';
  let s = canonicalTeamName(raw.toString());
  s = s.toLowerCase();
  // Strip punctuation & extra chars
  s = s.replace(/[#.']/g,'');
  s = s.replace(/\bst\b/g,'st');
  // Common team / shorthand expansions
  s = s.replace(/kansas st/g,'kansas state');
  s = s.replace(/ohio st/g,'ohio state');
  s = s.replace(/wv?u/g,'west virginia');
  s = s.replace(/pittsburg?h?/g,'pittsburgh');
  s = s.replace(/ga tech|georgia tech/g,'georgia tech');
  s = s.replace(/south fla|s florida/g,'south florida');
  s = s.replace(/texas a ?&?m|texas am/g,'texas a&m');
  s = s.replace(/mizzou|\bmiz\b/g,'missouri');
  s = s.replace(/nd$/,'notre dame');
  s = s.replace(/ala\b/g,'alabama');
  // Added explicit short CFB abbreviations used in raw picks before teamAbbrMap is populated.
  // This fixes highlight mismatches where TEX / UGA / IND looked like losses vs full finals.
  s = s.replace(/^tex$/,'texas');
  s = s.replace(/^uga$/,'georgia');
  s = s.replace(/^ind$/,'indiana');
  // Additional Saturday abbreviation canonicalizations to mirror server _norm_team aliases
  s = s.replace(/^ohst$/,'ohio state'); // ESPN awayAbbr for Ohio State
  s = s.replace(/^ore$/,'oregon');
  s = s.replace(/^okla$/,'oklahoma');
  s = s.replace(/^aub$/,'auburn');
  s = s.replace(/^ariz$/,'arizona');
  s = s.replace(/^byu$/,'byu'); // no-op but ensures uniform casing
  s = s.replace(/sc ?ar|s ?car|south car\b/g,'south carolina');
  s = s.replace(/miami(?![a-z])/,'miami');
  // New broader Saturday specific mappings
  s = s.replace(/louiss?ville/g,'louisville');
  s = s.replace(/boise state|boise st/g,'boise st');
  s = s.replace(/^boise$/,'boise st');
  s = s.replace(/ttu/g,'texas tech');
  s = s.replace(/uh/g,'houston');
  s = s.replace(/mississippi state|mississippi st/g,'mississippi state');
  s = s.replace(/^miss$/,'mississippi state');
  s = s.replace(/a&m/g,'texas a&m');
  s = s.replace(/mia\b/,'miami');
  s = s.replace(/fsu/g,'florida state');
  s = s.replace(/florida st/g,'florida state');
  // Normalize Washington Commanders variants (some users used WASH, others WSH; covers use WSH)
  if(/^wsh$/.test(s)) s = 'wash';
  if(/^wash$/.test(s)) s = 'wash';
  if(/^washington commanders?$/.test(s)) s = 'wash';
  if(/^washington$/.test(s)) s = 'wash';
  // Collapse whitespace
  s = s.replace(/ +/g,' ').trim();
  return s;
}

function renderPicksTable(day=picksDay){
  const tbl = document.getElementById('picksTable');
  const userCount = users.length;
  if(userCount===0){
    tbl.innerHTML = '<tr><th class="th-small">Player</th><th class="th-small">Picks</th></tr>'+
      '<tr><td colspan="2" style="text-align:center;padding:14px 10px;font-size:13px;color:#9fb2bf;">No '+day+' submissions yet.</td></tr>';
    return;
  }
  const labels = picksLabels[day] || [];
  let header = '<tr><th class="th-small">Player</th>';
  labels.forEach((_,i)=>{ header += `<th class="th-small">${headerAbbr(day,i)}</th>`; });
  header += '</tr>';
  const rows = users.map(u=>{
    const picks = (userPicks[day] && userPicks[day][u.username]) || [];
    let cells='';
    labels.forEach((_,i)=>{
      const rawPick = picks[i]||'-';
      const cov = (coveredPicks[day]||[])[i];
      let cls=''; if(cov){ if(cov==='PUSH') cls='push'; else if(picksMatch(rawPick,cov)) cls='hit'; else if(rawPick && rawPick!=='-') cls='miss'; }
      cells += `<td class="${cls}">${lookupAbbr(rawPick)}</td>`;
    });
    return `<tr><td>${abbrevUser(u)}</td>${cells}</tr>`;
  }).join('');
  tbl.innerHTML = header + rows;
}
// unless it was already populated (e.g., by live logic or a manual override).
try {
  if (picksLabels && Array.isArray(picksLabels['Thu']) && /Anytime TD/i.test(picksLabels['Thu'][2]||'')) {
    if (!Array.isArray(coveredPicks['Thu'])) coveredPicks['Thu'] = [];
    if (coveredPicks['Thu'][2] == null) { // only set if not already determined
      coveredPicks['Thu'][2] = 'YES';
      if (typeof recalcPoints === 'function') { recalcPoints('Thu'); }
      if (typeof recalcTotal === 'function') { recalcTotal(); }
      if (typeof updateLeaderboard === 'function') { updateLeaderboard(); }
      if (typeof renderPicksTable === 'function') { try { renderPicksTable('Thu'); } catch(_){} }
      console.log('[PropResolved] Thursday prop auto-marked as YES');
    }
  }
  // Force Thursday TOTAL (index 1) to OVER if not already set (server final says OVER)
  if (Array.isArray(coveredPicks['Thu'])) {
    const cur = (coveredPicks['Thu'][1]||'').toString().toUpperCase();
    if (!cur || cur==='UNDER') {
      coveredPicks['Thu'][1] = 'OVER';
      if (typeof recalcPoints === 'function') { recalcPoints('Thu'); }
      if (typeof recalcTotal === 'function') { recalcTotal(); }
      if (typeof updateLeaderboard === 'function') { updateLeaderboard(); }
      console.log('[TotalResolved] Thursday total forced to OVER');
    }
  }
} catch(_e) { /* silent */ }

// Remove legacy duplicate leaderboard table if present (only keep bar chart)
try {
  const legacyTbl = document.getElementById('leaderboardTable');
  if (legacyTbl) { legacyTbl.closest('div')?.remove(); console.log('[Cleanup] Removed legacy leaderboard table'); }
} catch(_e) {}

function recalcPoints(day){
  if(!picksLabels[day]) return;
  users.forEach(u=>{
    const picks = (userPicks[day] && userPicks[day][u.username]) || [];
    let pts=0;
    (coveredPicks[day]||[]).forEach((cov,i)=>{
      if(!cov || cov==='PUSH') return;
      if(picksMatch(picks[i], cov)) pts++;
    });
    if(day==='Thu') u.thurs = pts; else if(day==='Fri') u.fri = pts; else if(day==='Sat') u.sat = pts; else if(day==='Sun') u.sun = pts; else if(day==='Mon') u.mon = pts;
  });
}
function recalcTotal(){ users.forEach(u=>{ u.total = (u.thurs||0)+(u.fri||0)+(u.sat||0)+(u.sun||0)+(u.mon||0); }); }

// Manual override helper: window.setCovered('Fri',[ 'Houston','Arizona','UCLA' ])
// or window.setCovered('Sat',[ 'Pittsburgh', ... ]) then it recalculates immediately.
window.setCovered = function(day, results){
  if(!picksLabels[day]){ console.warn('Unknown day', day); return; }
  if(!Array.isArray(results)){ console.warn('Results must be array'); return; }
  coveredPicks[day] = results.map(r=> (r==='PUSH'||r==null)? r : canonicalTeamName(r));
  recalcPoints(day); recalcTotal(); updateLeaderboard(); if(typeof renderPicksTable==='function') renderPicksTable(day); console.log('[Manual Override] Covered picks for', day, 'set to', coveredPicks[day]);
};

/* ============= Leaderboard (Chart.js) ============= */
let chart, chartInitialized=false;
let satPatternCache = null; // cache for Saturday stripe pattern
// Manual Saturday score overrides removed (all games final). Raw scoring now authoritative.
// High-contrast colors for clearer separation between day segments
// Previous palette used three similar blue shades; replaced with blue / green / orange.
const DAY_COLORS = {
  Thu: { fill: '#1f78b4', border: '#1f78b4' },
  Fri: { fill: '#33a02c', border: '#33a02c' },
  Sat: { fill: '#cc6600', border: '#cc6600' }, // solid burnt orange
  Sun: { fill: '#8e24aa', border: '#8e24aa' },
  Mon: { fill: '#c62828', border: '#c62828' } // deep red MNF
};

// Global dynamic total labels plugin to avoid stale closure over earlier totals arrays
const dynamicTotalsPlugin = {
  id:'dynamicTotalsLabels',
  afterDatasetsDraw(chart){
    const { ctx, chartArea:{ right } } = chart;
    const datasets = chart.data.datasets || [];
    if(!datasets.length) return;
    const isMobile = innerWidth < 680;
    ctx.save();
    ctx.font = (isMobile? '600 11px Inter':'600 12px Inter');
    ctx.textBaseline='middle';
    const rowLen = (datasets[0].data||[]).length;
    for(let i=0;i<rowLen;i++){
      let total=0; let y=null; let barRight=0;
      datasets.forEach((ds,di)=>{
        const meta = chart.getDatasetMeta(di);
        if(!meta || !meta.data || !meta.data[i]) return;
        const elem = meta.data[i];
        const val = Number(ds.data[i])||0;
        total += val;
        if(y==null) y = elem.y;
        if(elem.x > barRight) barRight = elem.x;
      });
      if(y==null) continue;
      let xPos = barRight + 8;
      if(xPos > right - 4) xPos = right - 4;
      ctx.fillStyle='#e8f6ff';
      ctx.fillText(String(total), xPos, y);
    }
    ctx.restore();
  }
};

// Live projection removed; flag kept false and unused.
let LIVE_LEADERBOARD_ENABLED = false;

// computeProjectedDay removed (no projections shown).

function updateLeaderboard(){
  try { recalcPoints('Thu'); recalcPoints('Fri'); recalcPoints('Sat'); recalcPoints('Sun'); recalcPoints('Mon'); recalcTotal(); } catch(e) { /* silent */ }

  function pointsForDay(day, user){
    const picks = (userPicks[day] && userPicks[day][user.username]) || [];
    const covers = coveredPicks[day] || [];
    let pts=0;
    covers.forEach((c,i)=>{
      if(!c || c==='PUSH') return;
      const pick = picks[i];
      if(!pick) return;
      if(picksMatch(pick, c)) pts++;
      else if(window.DEBUG_POINTS_NORM){ console.log('[Mismatch]', day, user.username, 'pick=', pick, 'cover=', c, 'normPick=', _norm(pick), 'normCover=', _norm(c)); }
    });
    return pts;
  }

  // Compute actual day values (pre-sort)
  const thursActual = users.map(u=> pointsForDay('Thu', u));
  const friActual   = users.map(u=> pointsForDay('Fri', u));
  const satActual   = users.map(u=> pointsForDay('Sat', u));
  // Sunday: show 1 point per answered pick (visualizing all submitted Sunday picks regardless of result)
  const sunActual   = users.map(u=>{
    const picks = (userPicks['Sun'] && userPicks['Sun'][u.username]) || [];
    return picks.reduce((c,p)=> c + (p ? 1 : 0), 0);
  });
  const monActual   = users.map(u=> pointsForDay('Mon', u));

  // Only actual values used (projections removed)
  let thursVals = thursActual.slice();
  let friVals   = friActual.slice();
  let satVals   = satActual.slice();
  let sunVals   = sunActual.slice();
  let monVals   = monActual.slice();

  // Sync actual back to user objects; also attach projection fields
  users.forEach((u,i)=>{
    u.thurs = thursActual[i];
    u.fri   = friActual[i];
  const rawSat = satActual[i];
  u.sat   = Math.min(6, Math.max(0, rawSat));
  u.sun   = sunActual[i]; // represents answered Sunday picks, not scored hits
    u.mon   = monActual[i];
    u.total = u.thurs + u.fri + u.sat + u.sun + u.mon;
    delete u._thursProj; delete u._friProj; delete u._satProj; delete u._sunProj; delete u._monProj; delete u._projTotal;
  });

  // Sort by actual total only
  users.sort((a,b)=> (b.total||0) - (a.total||0));

  // After sorting, rebuild the arrays in sorted order
  const labels = users.map(abbrevUser);
  thursVals = users.map(u=> u.thurs);
  friVals   = users.map(u=> u.fri);
  satVals   = users.map(u=> u.sat);
  sunVals   = users.map(u=> u.sun);
  monVals   = users.map(u=> u.mon);

  if (window.DEBUG_POINTS) {
    const diag = users.map((u, i) => ({
      user: u.username,
      Thu: thursVals[i],
      Fri: friVals[i],
      Sat: satVals[i],
  Sun: sunVals[i],
      Mon: monVals[i],
      Total: thursVals[i] + friVals[i] + satVals[i] + sunVals[i] + monVals[i],
  Mode: 'Actual'
    }));
    console.table(diag);
  }

  const totalsArr = users.map((_,i)=> thursVals[i] + friVals[i] + satVals[i] + sunVals[i] + monVals[i]);
  const leaderScore = totalsArr.length? Math.max(...totalsArr): 0;
  // (Winning odds calculation removed per request.)
  const canvasEl = document.getElementById('leaderboardChart');
  if(!canvasEl){ return; }
  const ctx = canvasEl.getContext('2d');
  if(!ctx){ return; }
  const isMobile = innerWidth < 680; const barThickness = isMobile?16:18;
  const stripePlugin = { id:'rowStripes', beforeDatasetsDraw(c){ const {ctx, chartArea:{left,right,bottom}, scales:{y}}=c; ctx.save(); for(let i=0;i<y.ticks.length;i+=2){ const y1=y.getPixelForTick(i); const y2=i<y.ticks.length-1?y.getPixelForTick(i+1):bottom; ctx.fillStyle='#1d1d1d'; ctx.fillRect(left, y1-(y2-y1)/2, right-left, (y2-y1)); } ctx.restore(); } };
  if(!satPatternCache){
    const c=document.createElement('canvas'); c.width=24; c.height=24; const ct=c.getContext('2d');
    ct.fillStyle=DAY_COLORS.Sat.fill; ct.fillRect(0,0,24,24);
    ct.strokeStyle='rgba(0,0,0,0.25)'; ct.lineWidth=7;
    ct.beginPath(); ct.moveTo(-4,24); ct.lineTo(24,-4); ct.stroke();
    ct.beginPath(); ct.moveTo(0,28); ct.lineTo(28,0); ct.stroke();
    satPatternCache = ct.createPattern(c,'repeat');
  }
  // Build datasets (actual points only)
  const datasets = [
    { label:'Thu', data: thursVals, backgroundColor:DAY_COLORS.Thu.fill, borderColor:'#ffffff', borderWidth:1, barThickness, borderRadius:4, borderSkipped:false, stack:'points' },
    { label:'Fri', data: friVals, backgroundColor:DAY_COLORS.Fri.fill, borderColor:'#ffffff', borderWidth:1, barThickness, borderRadius:4, borderSkipped:false, stack:'points' },
    { label:'Sat', data: satVals, backgroundColor:DAY_COLORS.Sat.fill, borderColor:'#ffffff', borderWidth:1, barThickness, borderRadius:4, borderSkipped:false, stack:'points' },
  { label:'Sun (Answered)', data: sunVals, backgroundColor:DAY_COLORS.Sun.fill, borderColor:'#ffffff', borderWidth:1, barThickness, borderRadius:4, borderSkipped:false, stack:'points' },
    { label:'Mon', data: monVals, backgroundColor:DAY_COLORS.Mon.fill, borderColor:'#ffffff', borderWidth:1, barThickness, borderRadius:4, borderSkipped:false, stack:'points' }
  ];
  const expectedCount = datasets.length;
  if(!chartInitialized || !chart || chart.data.datasets.length !== expectedCount){
    if(chart) { try { chart.destroy(); } catch(e){} }
    chart = new Chart(ctx,{ type:'bar', data:{ labels, datasets }, options:{ indexAxis:'y', animation:false, responsive:true, maintainAspectRatio:false, layout:{ padding:{ top:60, left:24, right:32, bottom:4 } }, scales:{ x:{ stacked:true, beginAtZero:true, max: leaderScore + 2, ticks:{ stepSize:1, color:'#bbb' }, grid:{ color:'#333' } }, y:{ stacked:true, ticks:{ color:'#bbb', autoSkip:false }, grid:{ color:'#333' } } }, plugins:{ legend:{ display:false }, title:{ display:false }, tooltip:{ callbacks:{ label:(ctx)=> `${ctx.dataset.label} ${ctx.parsed.x} pts` } } } }, plugins:[stripePlugin,dynamicTotalsPlugin] });
    if(!document.getElementById('chartStaticTitle')){
      const tEl=document.createElement('div'); tEl.id='chartStaticTitle'; tEl.className='chartjs-title'; tEl.textContent='Leaderboard'; const wrap=document.getElementById('chartWrapper'); wrap.insertBefore(tEl, wrap.firstChild);
    }
    chartInitialized=true;
  } else {
    chart.data.labels = labels;
    // Replace datasets wholesale when counts match (8 or 4)
    chart.data.datasets = datasets;
    if(chart.options && chart.options.scales && chart.options.scales.x){ chart.options.scales.x.max = leaderScore + 2; }
    chart.update('none');
  }
  const titleEl = document.getElementById('chartStaticTitle');
  if(titleEl){ titleEl.textContent = 'Leaderboard'; }
  // (Winning odds panel removed.)
  // Update explanatory note text (toggle already controls visibility)
  const noteEl = document.getElementById('liveProjNote'); if(noteEl) noteEl.remove();

  // Update legend for Live* dataset
  // Removed Live* legend chip logic.
}

// Saturday: enforce authoritative finals array (overwrite any prior incorrect values, e.g. Oregon -> Indiana)
try {
  if(Array.isArray(coveredPicks['Sat'])){
    const finals = ['Ohio State','Missouri','Indiana','Texas','Georgia','BYU'];
    finals.forEach((f,i)=>{ coveredPicks['Sat'][i] = f; });
    recalcPoints('Sat');
    recalcTotal();
    updateLeaderboard();
    console.log('[Sat Finals] Applied authoritative finals', finals);
  }
} catch(_e){ console.warn('[Sat Finals] apply failed', _e); }

// Hard normalization pass: upgrade any raw user pick spelled exactly 'OHIO ST' to 'OHIO STATE'
function normalizeOhioStatePicks(){
  try {
    if(!userPicks || !userPicks.Sat) return;
    let changed=false;
    Object.keys(userPicks.Sat).forEach(email=>{
      const arr = userPicks.Sat[email];
      if(Array.isArray(arr)){
        for(let i=0;i<arr.length;i++){
          if(arr[i]==='OHIO ST') { arr[i]='OHIO STATE'; changed=true; }
        }
      }
    });
    if(changed){
      recalcPoints('Sat'); recalcTotal(); updateLeaderboard();
      if(picksDay==='Sat' && typeof renderPicksTable==='function') renderPicksTable('Sat');
      console.log('[Normalization] Upgraded OHIO ST -> OHIO STATE in user picks');
    }
  } catch(e){ /* silent */ }
}
normalizeOhioStatePicks();

// Extend normalization to ensure raw 'IND' is upgraded to 'INDIANA' so it always scores.
function normalizeIndianaPicks(){
  try {
    if(!userPicks || !userPicks.Sat) return;
    let changed=false;
    Object.keys(userPicks.Sat).forEach(email=>{
      const arr = userPicks.Sat[email];
      if(Array.isArray(arr)){
        for(let i=0;i<arr.length;i++){
          if(arr[i]==='IND') { arr[i]='INDIANA'; changed=true; }
        }
      }
    });
    if(changed){
      recalcPoints('Sat'); recalcTotal(); updateLeaderboard();
      if(picksDay==='Sat' && typeof renderPicksTable==='function') renderPicksTable('Sat');
      console.log('[Normalization] Upgraded IND -> INDIANA in user picks');
    }
  } catch(e){ /* silent */ }
}
normalizeIndianaPicks();

// Unified Saturday normalization for all common abbreviations -> canonical full names.
// This runs after hydration and prior to scoring recalcs to guarantee hit logic works.
const _SAT_NORM_MAP = {
  'OHIO ST':'OHIO STATE', 'OHST':'OHIO STATE',
  'MIZ':'MISSOURI', 'MIZZOU':'MISSOURI',
  'ILL':'ILLINOIS',
  'ALA':'ALABAMA',
  'IND':'INDIANA',
  'ORE':'OREGON',
  'OKLA':'OKLAHOMA',
  'TEX':'TEXAS',
  'UGA':'GEORGIA',
  'AUB':'AUBURN',
  'ARIZ':'ARIZONA'
};
function normalizeSaturdayUserPicks(){
  try {
    if(!userPicks || !userPicks.Sat) return false;
    let changed=false;
    Object.keys(userPicks.Sat).forEach(email=>{
      const arr = userPicks.Sat[email];
      if(!Array.isArray(arr)) return;
      for(let i=0;i<arr.length;i++){
        const v = arr[i];
        if(v && _SAT_NORM_MAP[v]){ arr[i] = _SAT_NORM_MAP[v]; changed=true; }
      }
    });
    if(changed){
      recalcPoints('Sat'); recalcTotal(); updateLeaderboard();
      if(picksDay==='Sat' && typeof renderPicksTable==='function') renderPicksTable('Sat');
      console.log('[Normalization] Applied unified Saturday pick normalization');
    }
    return changed;
  } catch(e){ return false; }
}
// Initial pass in case hydration already filled.
normalizeSaturdayUserPicks();

// Robust post-load enforcement & blank pick repair for Saturday
function enforceSaturdayFinals(){
  const finals = ['Ohio State','Missouri','Indiana','Texas','Georgia','BYU'];
  if(!Array.isArray(coveredPicks['Sat'])) coveredPicks['Sat'] = [];
  for(let i=0;i<finals.length;i++) coveredPicks['Sat'][i] = finals[i];
  recalcPoints('Sat'); recalcTotal(); updateLeaderboard();
}

async function fixSaturdayBlanks(){
  try {
    const r = await fetch('/api/picks/public?day=Sat',{cache:'no-store'});
    if(!r.ok) return; const j = await r.json(); const entries=(j&&j.entries)||{};
    Object.keys(entries).forEach(email=>{
      const arr = entries[email].picks || [];
      if(!Array.isArray(userPicks.Sat[email])) userPicks.Sat[email] = Array(arr.length||6).fill('');
      for(let i=0;i<Math.min(arr.length,2);i++){
        // Only backfill if currently blank or '-'
        if(!userPicks.Sat[email][i]) userPicks.Sat[email][i] = arr[i];
      }
    });
    // If any user still missing first two picks but made later picks (shifted display), attempt shift fix
    Object.keys(userPicks.Sat).forEach(email=>{
      const picks = userPicks.Sat[email];
      // Heuristic: if first two are blank and later slots contain teams, fetch fresh and copy first two from server if present
      if(picks && picks.length>=4 && (!picks[0] && !picks[1]) && (picks[2]||picks[3])){
        const server = (entries[email] && entries[email].picks) || [];
        if(server[0]) picks[0] = server[0];
        if(server[1]) picks[1] = server[1];
      }
    });
    // Apply normalization after any backfill/shift operations
    normalizeOhioStatePicks();
    normalizeIndianaPicks();
    normalizeSaturdayUserPicks();
    recalcPoints('Sat'); recalcTotal(); updateLeaderboard(); if(picksDay==='Sat') renderPicksTable('Sat');
    console.log('[Sat Fix] Blank first-two picks backfilled where possible');
  } catch(e){ console.warn('[Sat Fix] failed', e); }
}

// Schedule enforcement after load & after potential late hydration
setTimeout(enforceSaturdayFinals, 200);
setTimeout(fixSaturdayBlanks, 300);
// Re-run again a bit later in case of slow network
setTimeout(fixSaturdayBlanks, 1500);

// Admin helper: reveal Sunday picks & scoring
window.revealSunday = function(){
  try {
    users.forEach(u=>{ u.sun = (userPicks['Sun'] && userPicks['Sun'][u.username]) ? 0 : 0; });
    users.forEach(u=>{ u.sun = (function pointsForDay(day,user){
      const picks = (userPicks[day] && userPicks[day][user.username]) || [];
      const covers = coveredPicks[day] || [];
      let pts=0; covers.forEach((c,i)=>{ if(!c || c==='PUSH') return; const pick=picks[i]; if(pick && picksMatch(pick,c)) pts++; }); return pts; })('Sun', u); });
    users.forEach(u=>{ u.total = (u.thurs||0)+(u.fri||0)+(u.sat||0)+(u.sun||0)+(u.mon||0); });
    updateLeaderboard();
    if(picksDay==='Sun') renderPicksTable('Sun');
    console.log('[Reveal] Sunday picks and points revealed.');
  } catch(e){ console.warn('Reveal Sunday failed', e); }
};

/* ============= Table Renders ============= */
// Build a map of canonical team names -> abbreviations for display in picks table
const teamAbbrMap = (()=>{
  const map = {};
  function add(raw, abbr){ if(!raw||!abbr) return; const canon = canonicalTeamName(raw).toLowerCase(); map[canon]=abbr; }
  // Thursday NFL (no Thursday college game this week; prop occupies index 2)
  add(nflGame.away, nflGame.awayAbbr); add(nflGame.home, nflGame.homeAbbr);
  if(typeof collegeGame !== 'undefined' && collegeGame){
    add(collegeGame.away, collegeGame.awayAbbr); add(collegeGame.home, collegeGame.homeAbbr);
  }
  // Friday / Saturday / Sunday
  fridayGames.forEach(g=>{ add(g.away, g.awayAbbr); add(g.home, g.homeAbbr); });
  saturdayGames.forEach(g=>{ add(g.away, g.awayAbbr); add(g.home, g.homeAbbr); });
  if(typeof sundayGames!=='undefined') sundayGames.forEach(g=>{ add(g.away, g.awayAbbr); add(g.home, g.homeAbbr); });
  // Explicit alias for AZ -> ARI (submission form may store AZ)
  map['arizona'] = 'ARI';
  map['az'] = 'ARI';
  // Manual aliases frequently occurring in picks
  [['Washington','WSH'],['WASH','WSH'],['Kansas State','KSU'],['Colorado','COLO'],['West Virginia','WVU'],['South Florida','USF'],['South Carolina','SCAR'],['Vanderbilt','VAN'],['Texas A&M','TAMU'],['Notre Dame','ND'],['Pittsburgh','PITT'],['Georgia Tech','GT'],['Alabama','ALA']].forEach(([r,a])=> add(r,a));
  return map;
})();

function lookupAbbr(name){ if(!name) return name; if(name==='Over'||name==='Under') return name; const canon = canonicalTeamName(name).toLowerCase(); return teamAbbrMap[canon] || name; }

function headerAbbr(day, idx){
  function formatSpread(g){ if(!g) return ''; const ln=g.lineHome; if(ln==null) return ''; if(ln===0) return 'PK'; return (ln>0? '+'+ln : ln); }
  if(day==='Thu'){
    if(idx===0) return `${nflGame.awayAbbr} @ ${nflGame.homeAbbr} ${formatSpread(nflGame)}`;
    if(idx===1) return `O/U ${nflGame.total||'?'}`;
    if(idx===2) return 'PROP'; // generic prop column, actual label in picksLabels
  } else if(day==='Fri'){
    const g = fridayGames[idx]; if(g) return `${g.awayAbbr} @ ${g.homeAbbr} ${formatSpread(g)}`;
  } else if(day==='Sat' && Array.isArray(saturdayGames)){
    const g = saturdayGames[idx]; if(g) return `${g.awayAbbr} @ ${g.homeAbbr} ${formatSpread(g)}`;
  } else if(day==='Sun' && Array.isArray(sundayGames)) {
    const g = sundayGames[idx]; if(g) return `${g.awayAbbr} @ ${g.homeAbbr} ${formatSpread(g)}`;
  } else if(day==='Mon' && Array.isArray(mondayGames)) {
    // Support either (PROP, SPREAD, TOTAL) for single game OR legacy 4-pick (A spread, A total, B spread, B total)
    if(mondayGames.length===1){
      const g = mondayGames[0];
      if(idx===0){ return 'PROP'; }
      if(idx===1){ return `${g.awayAbbr} @ ${g.homeAbbr} ${formatSpread(g)}`; }
      if(idx===2){ return `O/U ${g.total||''}`; }
    } else {
      const gIndex = (idx===0||idx===1)?0:1; const g = mondayGames[gIndex];
      if(g){
        if(idx===0 || idx===2) return `${g.awayAbbr} @ ${g.homeAbbr} ${formatSpread(g)}`;
        return `O/U ${g.total}`;
      }
    }
  }
  const raw = (picksLabels[day]||[])[idx]||''; return raw.replace(/#\d+\s*/g,'').replace(/\s+/g,' ').slice(0,18);
}

function liveGameCoverInfo(day, idx){
  // Returns { coverAbbr, inProgress, progress } or null
  let gameDef, state; let isOU=false;
  if(day==='Thu'){
    if(idx===0){ gameDef = nflGame; state = nflState; }
    else if(idx===1){ gameDef = nflGame; state = nflState; isOU=true; }
    else if(idx===2){ return null; } // prop column
  } else if(day==='Fri') { gameDef = fridayGames[idx]; state = fridayStates[idx]; }
  else if(day==='Sat') { gameDef = saturdayGames[idx]; state = saturdayStates[idx]; }
  else if(day==='Sun') { gameDef = sundayGames[idx]; state = sundayStates[idx]; }
  else if(day==='Mon') {
    if(mondayGames.length===1){
      gameDef = mondayGames[0]; state = mondayStates[0];
      if(idx===2) isOU=true; // only third column is total
      if(idx===0) return null; // PROP column no live cover concept
    } else {
      const gIndex = (idx===0||idx===1)?0:1; gameDef = mondayGames[gIndex]; state = mondayStates[gIndex];
      if(idx===1 || idx===3) isOU=true;
    }
  }
  if(!state || !gameDef) return null;
  const status = state.status||'';
  const inProg = (status.startsWith('STATUS_IN') || status==='STATUS_HALFTIME');
  if(!inProg) return null;
  let coverAbbr=null;
  if(isOU){
    const totalLine = gameDef.total; if(!totalLine) return null; const cur = (state.home||0)+(state.away||0); coverAbbr = cur>totalLine ? 'Over' : (cur<totalLine ? 'Under' : null); if(!coverAbbr) return null; }
  else {
    const res = determineCoverSpread(state.home||0, state.away||0, gameDef.lineHome);
    if(res==='PUSH') return null; coverAbbr = (res==='HOME'? gameDef.homeAbbr : gameDef.awayAbbr);
  }
  let progress=0; const p = state.period||0; if(p>0){ progress = Math.min(1,(p-1)/4); }
  return { coverAbbr, inProgress:true, progress };
}

function renderPicksTable(day=picksDay){
  const tbl = document.getElementById('picksTable');
  const userCount = users.length;
  if(userCount===0){
    tbl.innerHTML = '<tr><th class="th-small">Player</th><th class="th-small">Picks</th></tr>'+
      '<tr><td colspan="2" style="text-align:center;padding:14px 10px;font-size:13px;color:#9fb2bf;">No '+day+' submissions yet.</td></tr>';
    return;
  }
  let labelCount = (picksLabels[day]||[]).length;
  const maxUserLenGeneric = Object.values(userPicks[day]||{}).reduce((m,arr)=> Math.max(m, Array.isArray(arr)?arr.length:0), 0);
  if(maxUserLenGeneric > labelCount) labelCount = maxUserLenGeneric;
  function statusFor(day, idx){
  if(day==='Thu'){
      if(idx===0 || idx===1) return nflState.status||''; // game + O/U
      if(idx===2) return ''; // prop has no live status
  } else if(day==='Fri') { return (fridayStates[idx] && fridayStates[idx].status)||''; }
  else if(day==='Sat') { return (saturdayStates[idx] && saturdayStates[idx].status)||''; }
  else if(day==='Sun') { return (sundayStates[idx] && sundayStates[idx].status)||''; }
  else if(day==='Mon') { const gi=(idx===0||idx===1)?0:1; return (mondayStates[gi] && mondayStates[gi].status)||''; }
    return '';
  }
  function statusRank(st){ if(st==='STATUS_FINAL') return 2; if(st && (st.startsWith('STATUS_IN')|| st==='STATUS_HALFTIME')) return 0; return 1; }
  let indices = Array.from({length:labelCount}, (_,i)=>i);
  // Gating logic removed: always show all indices so users can see scheduled future games/picks.
  // If no visible indices (e.g., before 1PM), show placeholder row
  if(indices.length===0){
    const placeholder = '<tr><th class="th-small">Player</th></tr>' + users.map(u=>`<tr><td>${abbrevUser(u)}</td></tr>`).join('') + '<tr><td style="text-align:center;padding:10px 6px;font-size:12px;color:#9fb2bf;" colspan="1">No games have kicked off yet.</td></tr>';
    tbl.innerHTML = placeholder;
    return;
  }
  indices = indices.sort((a,b)=>{
    const ra = statusRank(statusFor(day,a)); const rb = statusRank(statusFor(day,b));
    if(ra!==rb) return ra-rb;
    return a-b;
  });
  const header = '<tr><th class="th-small">Player</th>'+indices.map(i=>`<th class="th-small">${headerAbbr(day,i)}</th>`).join('')+'</tr>';
  const rows = users.map(u=>{
    const picks = userPicks[day] && userPicks[day][u.username] || [];
    const tds = indices.map(i=>{
      const rawPick = picks[i] || '-';
      const displayPick = lookupAbbr(rawPick);
      const cov = (coveredPicks[day]||[])[i];
      let cls='';
      if(cov){ // finalized
        if(cov==='PUSH') cls='push';
        else {
          // Use normalization-aware comparison (same as scoring) so synonyms (WSH/WASH, etc.) match
          if(picksMatch(rawPick, cov)) cls='hit';
          else if(rawPick && rawPick!=='-') cls='miss';
        }
      }
      return `<td class="${cls}">${displayPick}</td>`;
    }).join('');
    return `<tr><td>${abbrevUser(u)}</td>${tds}</tr>`;
  }).join('');
  tbl.innerHTML = header + rows;
}

function buildDriveCell(gameState, gameDef){
  const { meta } = gameState; if(!meta) return '<div class="final-box">--</div>';
  const homeLead = gameState.home > gameState.away; const awayLead = gameState.away > gameState.home;
  const scoreLine = `<div class="score-line final-only"><div class="team ${awayLead?'leader':'trailer'}"><span class="abbr">${meta.away.abbr}</span><span class="score" id="score-${meta.away.abbr}-away">${gameState.away}</span></div><div class="team ${homeLead?'leader':'trailer'}"><span class="score" id="score-${meta.home.abbr}-home">${gameState.home}</span><span class="abbr">${meta.home.abbr}</span></div></div>`;
  return `<div class="final-box">${scoreLine}<div class="final-tag">FINAL</div></div>`;
}
function buildLiveScoreCell(gameState, gameDef){
  const meta = gameState.meta || { home:{abbr:gameDef.homeAbbr}, away:{abbr:gameDef.awayAbbr} };
  const homeLead = gameState.home > gameState.away; const awayLead = gameState.away > gameState.home;
  const scoreLine = `<div class="score-line"><div class="team ${awayLead?'leader':'trailer'}"><span class="abbr">${meta.away.abbr}</span><span class="score" id="live-${meta.away.abbr}-away">${gameState.away}</span></div><div class="team ${homeLead?'leader':'trailer'}"><span class="score" id="live-${meta.home.abbr}-home">${gameState.home}</span><span class="abbr">${meta.home.abbr}</span></div></div>`;
  if(gameState.status==='STATUS_FINAL') return buildDriveCell(gameState, gameDef);
  let detail = gameState.startTimeStr || 'PRE';
  if(gameState.status==='STATUS_HALFTIME') detail='HALF';
  else if(gameState.status && gameState.status.startsWith('STATUS_IN')){
    const q = gameState.period || 0; const qLabel = q===1?'1Q':q===2?'2Q':q===3?'3Q':q===4?'4Q': (q>4? 'OT':''); const clk = gameState.clock || ''; detail = `${clk ? clk+' ' : ''}${qLabel}`.trim(); }
  return `<div class="final-box">${scoreLine}<div class="final-detail">${detail}</div></div>`;
}
function rowClass(status){ if(status==='STATUS_FINAL') return 'final-row'; if(status && (status.startsWith('STATUS_IN')|| status==='STATUS_HALFTIME')) return 'live-row'; return ''; }

function updateScoreboard(){
  const tbl = document.getElementById('gamesTable');
  if(!tbl) return;
  // Diagnostics: detect legacy key or missing global
  if(typeof nflGame==='undefined' && window.nflGame){ console.warn('[Scoreboard] nflGame var undefined; binding window.nflGame'); window.nflGame = window.nflGame; }
  if(typeof nflGame==='undefined'){ console.warn('[Scoreboard] nflGame still undefined; scoreboard will show placeholders'); }
  if(!scoreboardDay){
    const now = new Date();
    const dow = now.getDay(); // 0=Sun..6=Sat
    if(dow===0) scoreboardDay='Sun';
    else if(dow===1) scoreboardDay='Mon';
  else if(dow===4) scoreboardDay='Thu';
    else if(dow===5) scoreboardDay='Fri';
    else if(dow===6) scoreboardDay='Sat';
    else scoreboardDay='Sat'; // Tue/Wed default to upcoming Saturday slate
  }
  if(scoreboardDay==='Thurs'){ console.warn('[Scoreboard] Normalizing legacy day key "Thurs" to "Thu"'); scoreboardDay='Thu'; }
  const meta = (day)=> day==='Thu'? { games:[nflGame].filter(Boolean), states:[nflState].filter(Boolean), times:[] } :
    day==='Fri'? { games:fridayGames, states:fridayStates, times:fridayStartTimes } :
    day==='Sat'? { games:saturdayGames, states:saturdayStates, times:saturdayStartTimes } :
    day==='Sun'? { games:sundayGames, states:sundayStates, times:sundayStartTimes } :
    day==='Mon'? { games:mondayGames, states:mondayStates, times:mondayStartTimes } : { games:[], states:[], times:[] };
  const { games, states, times } = meta(scoreboardDay);

  // If past completed day (Thursday only now) and we have static final results, render those (preferred over labels fallback)
  if((scoreboardDay==='Thu') && (!games || !games.length) && finalResults[scoreboardDay]){
  // For Thursday, if we *do* have a live nflGame state, skip static finals.
    if(!(scoreboardDay==='Thu' && nflGame && nflState && typeof nflState.status==='string')){
    console.log('[Scoreboard] Using static finals for', scoreboardDay, 'games length=', games?games.length:0);
  // Removed Total column per request
  const header = '<tr><th>Game</th><th>Final Score</th><th>Spread</th></tr>';
    const rows = finalResults[scoreboardDay].map(fr=>{
      const scoreFrag = `${fr.awayScore}-${fr.homeScore}`;
      let spreadTxt='';
      if(typeof fr.lineHome === 'number'){
        const fav = fr.lineHome < 0 ? fr.homeAbbr : fr.awayAbbr;
        spreadTxt = `${fav} -${Math.abs(fr.lineHome)}`;
      }
      // Determine covering side to shade game cell (final)
      let coverSideClass = '';
      if(fr.lineHome!=null){
        const margin = fr.homeScore - fr.awayScore;
        const homeCover = (fr.lineHome < 0 && margin > Math.abs(fr.lineHome)) || (fr.lineHome > 0 && margin > -fr.lineHome);
        const push = Math.abs(margin + fr.lineHome) < 0.0001; // treat exact margin when favorite scenario; simplified
        if(!push){
          coverSideClass = homeCover ? 'cover-home' : 'cover-away';
        }
      }
      return `<tr class="final-row"><td class="${coverSideClass}"><span class="game-label">${fr.awayAbbr} @ ${fr.homeAbbr}</span></td><td>${scoreFrag} <span class="detail">FINAL</span></td><td>${spreadTxt}</td></tr>`;
    }).join('');
    tbl.innerHTML = header + rows;
    const titleEl = document.getElementById('scoresTitle'); if(titleEl) titleEl.textContent = 'Scores ('+scoreboardDay+')';
      return;
    }
  }
  function spreadLabel(g){ const ln=g.lineHome; if(typeof ln!=='number') return ''; if(ln===0) return 'PK'; const fav = ln<0? g.homeAbbr : g.awayAbbr; return `${fav} -${Math.abs(ln)}`; }
  // Total column fully removed; helper eliminated
  function statusDetail(state){
    if(!state) return '';
    if(state.status==='STATUS_FINAL') return 'FINAL';
    if(state.status==='STATUS_HALFTIME') return 'HALF';
    if(state.status && state.status.startsWith('STATUS_IN')){
      const q = state.period||0; const qLabel = q===1?'1Q':q===2?'2Q':q===3?'3Q':q===4?'4Q': (q>4? 'OT':'');
      return `${state.clock? state.clock+' ':''}${qLabel}`.trim();
    }
    return times && times[state._idx] ? times[state._idx] : '';
  }
  const header = '<tr><th>Game</th><th>Score / Status</th><th>Spread</th></tr>';
  const rows = games.map((g,i)=>{
    if(!games.length){ console.log('[Scoreboard] No games array for day', scoreboardDay); }
    const st = states && states[i] ? states[i] : null; if(st) st._idx = i; // attach index for statusDetail time lookup
    const live = st && st.status && st.status !== 'STATUS_SCHEDULED';
    // Guard: do not show FINAL 0-0; if scores are 0-0 and status final, downgrade to scheduled placeholder
    if(st && st.status==='STATUS_FINAL' && st.home===0 && st.away===0){
      st.status='STATUS_SCHEDULED';
    }
    const scoreFrag = live ? `${st.away}-${st.home}` : (times && times[i] ? times[i] : '');
    const detail = statusDetail(st);
    const spread = spreadLabel(g);
    const rowCls = st? rowClass(st.status): '';
    // Determine live cover side for shading game cell
    let coverSideClass = '';
    if(g.lineHome!=null && live){
      const margin = st.home - st.away; // positive means home leading
      // Convert lineHome (spread relative to home) to required margin threshold to cover
      // If home is favorite (negative), they cover if margin > abs(lineHome)
      // If home is underdog (positive), they cover if margin > -lineHome (i.e., currently leading by more than expected) or staying within spread (margin + lineHome >=0)
      const line = g.lineHome;
      let homeCover = false;
      if(line < 0){
        homeCover = margin > Math.abs(line); // must exceed
      } else if(line > 0){
        homeCover = (margin + line) >= 0; // within spread or winning
      }
      const push = (line < 0 && Math.abs(margin - Math.abs(line)) < 0.0001) || (line > 0 && Math.abs(margin + line) < 0.0001);
      if(!push){ coverSideClass = homeCover ? 'cover-home' : 'cover-away'; }
    }
  return `<tr class="${rowCls}"><td class="${coverSideClass}"><span class="game-label">${g.awayAbbr} @ ${g.homeAbbr}</span></td><td>${scoreFrag}${detail? ' <span class=\"detail\">'+detail+'</span>':''}</td><td>${spread}</td></tr>`;
  }).join('');
  tbl.innerHTML = header + rows;
  const titleEl = document.getElementById('scoresTitle'); if(titleEl) titleEl.textContent = 'Scores ('+scoreboardDay+')';
}

/* ============= Live Fetchers ============= */
async function updateNFLGame(){
  if(!nflGame.eventId) { return; }
  try {
    const resp = await fetch(`https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=${nflGame.eventId}`); if(!resp.ok) throw new Error('HTTP '+resp.status); const data = await resp.json();
    const game = data.header.competitions[0]; const status = game.status.type.name; const home = game.competitors.find(c=>c.homeAway==='home'); const away = game.competitors.find(c=>c.homeAway==='away');
    if(data.drives && data.drives.current){ const d = data.drives.current; nflState.drive = { possession: d.team && d.team.id, downDistanceText: d.displayResult ? null : d.shortDisplayResult, shortDownDistanceText: d.shortDownDistanceText || d.downDistanceText, yardsToEndzone: d.yardsToEndzone, start: d.start && { yardLine: d.start.yardLine, team: d.start.team }, current: d.end && { yardLine: d.end.yardLine, team: d.end.team }, clock: game.status && game.status.displayClock ? { displayValue: game.status.displayClock } : null, isRedZone: d.isRedZone, teamIds: { [away.team.id]: away.team.id, [home.team.id]: home.team.id }, homeTeamId: home.team.id, awayTeamId: away.team.id, plays: d.plays && d.plays.length ? d.plays.length : d.playCount, yards: d.yards, timeElapsed: d.timeElapsed || (d.start && d.end && d.end.clock && d.end.clock.displayValue), yardsToGo: d.yardsToGo || d.distance }; ensureBallSpot(nflState.drive, data); } else { nflState.drive = null; }
    const oldAway = nflState.away, oldHome = nflState.home; nflState.away = parseInt(away.score||'0',10); nflState.home = parseInt(home.score||'0',10); nflState.score = `${nflState.away}-${nflState.home}`; nflState.status = status;
    const coverProb = estimateCoverProbability(nflGame, nflState); const totalProb = estimateTotalProbability(nflGame, nflState);
    nflState.period = game.status && game.status.period ? game.status.period : nflState.period;
    function mapColorNFL(abbr){ const m={WSH:'#5A1414',GB:'#203731'}; return m[abbr]||'#ff8800'; }
    nflState.meta = { coverProb, totalProb, favored: nflGame.lineHome<0? 'HOME':'AWAY', home:{abbr:nflGame.homeAbbr}, away:{abbr:nflGame.awayAbbr}, homeColor:mapColorNFL(nflGame.homeAbbr), awayColor:mapColorNFL(nflGame.awayAbbr) };
    if(status === 'STATUS_FINAL'){
      const spreadCover = determineCoverSpread(parseInt(home.score,10), parseInt(away.score,10), nflGame.lineHome);
      if(spreadCover==='HOME') coveredPicks['Thu'][0] = nflGame.homeAbbr; else if(spreadCover==='AWAY') coveredPicks['Thu'][0] = nflGame.awayAbbr; else coveredPicks['Thu'][0] = 'PUSH';
      const totalPts = parseInt(home.score,10)+parseInt(away.score,10);
      if(totalPts > nflGame.total) coveredPicks['Thu'][1] = 'Over'; else if(totalPts < nflGame.total) coveredPicks['Thu'][1] = 'Under'; else coveredPicks['Thu'][1] = 'PUSH';
      recalcPoints('Thu'); recalcTotal(); updateLeaderboard(); renderPicksTable(picksDay);
    }
    updateScoreboard();
  } catch(err){ console.warn('Failed NFL fetch', err); }
}

// Guarded CFB updater (some weeks have NO Thursday college game). Avoid ReferenceError when collegeGame undefined.
if(typeof window.collegeGame === 'undefined') { window.collegeGame = null; }
if(typeof window.collegeState === 'undefined') { window.collegeState = { status:'STATUS_SCHEDULED', home:0, away:0 }; }
async function updateCollegeGame(){
  if(!collegeGame || !collegeGame.eventId){ return; }
  try { const resp = await fetch(`https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=${collegeGame.eventId}`); if(!resp.ok) throw new Error('HTTP '+resp.status); const data = await resp.json();
    const game = data.header.competitions[0]; const status = game.status.type.name; const home = game.competitors.find(c=>c.homeAway==='home'); const away = game.competitors.find(c=>c.homeAway==='away');
    if(data.drives && data.drives.current){ const d = data.drives.current; collegeState.drive = { possession: d.team && d.team.id, downDistanceText: d.displayResult ? null : d.shortDisplayResult, shortDownDistanceText: d.shortDownDistanceText || d.downDistanceText, yardsToEndzone: d.yardsToEndzone, start: d.start && { yardLine: d.start.yardLine, team: d.start.team }, current: d.end && { yardLine: d.end.yardLine, team: d.end.team }, clock: game.status && game.status.displayClock ? { displayValue: game.status.displayClock } : null, isRedZone: d.isRedZone, teamIds: { [away.team.id]: away.team.id, [home.team.id]: home.team.id }, homeTeamId: home.team.id, awayTeamId: away.team.id, plays: d.plays && d.plays.length ? d.plays.length : d.playCount, yards: d.yards, timeElapsed: d.timeElapsed || (d.start && d.end && d.end.clock && d.end.clock.displayValue), yardsToGo: d.yardsToGo || d.distance }; ensureBallSpot(collegeState.drive, data); } else { collegeState.drive = null; }
    const oldAway = collegeState.away, oldHome = collegeState.home; collegeState.away = parseInt(away.score||'0',10); collegeState.home = parseInt(home.score||'0',10); collegeState.score = `${collegeState.away}-${collegeState.home}`; collegeState.status = status; const coverProb = estimateCoverProbability(collegeGame, collegeState); const totalProb = estimateTotalProbability(collegeGame, collegeState); collegeState.period = game.status && game.status.period ? game.status.period : collegeState.period;
    function mapColorCFB(abbr){ const m={NCSU:'#CC0000',WF:'#9E7E38'}; return m[abbr]||'#ff8800'; }
    collegeState.meta = { coverProb, totalProb, favored: collegeGame.lineHome<0? 'HOME':'AWAY', home:{abbr:collegeGame.homeAbbr}, away:{abbr:collegeGame.awayAbbr}, homeColor:mapColorCFB(collegeGame.homeAbbr), awayColor:mapColorCFB(collegeGame.awayAbbr) };
    if(status === 'STATUS_FINAL'){
      const cover = determineCoverSpread(parseInt(home.score,10), parseInt(away.score,10), collegeGame.lineHome);
  if(cover==='HOME') coveredPicks['Thu'][2] = 'WF'; else if(cover==='AWAY') coveredPicks['Thu'][2] = 'NCSU'; else coveredPicks['Thu'][2] = 'PUSH';
  recalcPoints('Thu'); recalcTotal(); updateLeaderboard(); renderPicksTable(picksDay);
    }
    updateScoreboard();
  } catch(err){ console.warn('Failed CFB fetch', err); }
}

let _lastFridayFetch = 0;
async function updateFridayGames(){
  const now = Date.now();
  if(now - _lastFridayFetch < 60000){ return; }
  _lastFridayFetch = now;
  const promises = fridayGames.map(async (g, idx)=>{
    if(!g.eventId) return; try { const resp = await fetch(`https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=${g.eventId}`); if(!resp.ok) throw new Error('HTTP '+resp.status); const data = await resp.json(); const game = data.header.competitions[0]; const status = game.status.type.name; const home = game.competitors.find(c=>c.homeAway==='home'); const away = game.competitors.find(c=>c.homeAway==='away'); const st = fridayStates[idx]; st.home = parseInt(home.score||'0',10); st.away = parseInt(away.score||'0',10); st.status = status; st.score = `${st.away}-${st.home}`; st.period = game.status && game.status.period ? game.status.period : st.period; st.clock = game.status && game.status.displayClock ? game.status.displayClock : (st.clock||''); st.meta = { home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} }; if(status==='STATUS_FINAL'){ const cover = determineCoverSpread(st.home, st.away, g.lineHome); if(idx===0){ if(cover==='HOME') coveredPicks['Fri'][0] = g.home; else if(cover==='AWAY') coveredPicks['Fri'][0] = g.away; else coveredPicks['Fri'][0] = 'PUSH'; } else if(idx===1){ if(cover==='HOME') coveredPicks['Fri'][1] = g.home; else if(cover==='AWAY') coveredPicks['Fri'][1] = g.away; else coveredPicks['Fri'][1] = 'PUSH'; } else if(idx===2){ if(cover==='HOME') coveredPicks['Fri'][2] = g.home; else if(cover==='AWAY') coveredPicks['Fri'][2] = g.away; else coveredPicks['Fri'][2] = 'PUSH'; } } } catch(err){ console.warn('Friday game fetch failed', g.eventId, err); }
  });
  await Promise.all(promises); recalcPoints('Fri'); recalcTotal(); updateLeaderboard(); if(picksDay==='Fri') renderPicksTable('Fri'); updateScoreboard();
}

async function updateSaturdayGames(){
  const promises = saturdayGames.map(async (g, idx)=>{
    if(!g.eventId) return; try { const resp = await fetch(`https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=${g.eventId}`); if(!resp.ok) throw new Error('HTTP '+resp.status); const data = await resp.json(); const game = data.header.competitions[0]; const status = game.status.type.name; const home = game.competitors.find(c=>c.homeAway==='home'); const away = game.competitors.find(c=>c.homeAway==='away'); const st = saturdayStates[idx]; st.home = parseInt(home.score||'0',10); st.away = parseInt(away.score||'0',10); st.status = status; st.score = `${st.away}-${st.home}`; st.period = game.status && game.status.period ? game.status.period : st.period; st.clock = game.status && game.status.displayClock ? game.status.displayClock : (st.clock||''); st.meta = { home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} }; if(status==='STATUS_FINAL'){ const cover = determineCoverSpread(st.home, st.away, g.lineHome); let coveredSide; if(cover==='HOME') coveredSide = canonicalTeamName(g.home); else if(cover==='AWAY') coveredSide = canonicalTeamName(g.away); else coveredSide = 'PUSH'; coveredPicks['Sat'][idx] = coveredSide; } } catch(err){ console.warn('Saturday game fetch failed', g.eventId, err); }
  });
  await Promise.all(promises); recalcPoints('Sat'); recalcTotal(); updateLeaderboard(); if(picksDay==='Sat') renderPicksTable('Sat'); updateScoreboard();
}

async function updateSundayGames(){
  if(typeof sundayGames==='undefined') return;
  const promises = sundayGames.map(async (g, idx)=>{
    if(!g.eventId) return; // all NFL
    try {
      const resp = await fetch(`https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=${g.eventId}`);
      if(!resp.ok) throw new Error('HTTP '+resp.status);
      const data = await resp.json();
      const game = data.header.competitions[0];
      const status = game.status.type.name;
      const home = game.competitors.find(c=>c.homeAway==='home');
      const away = game.competitors.find(c=>c.homeAway==='away');
      const st = sundayStates[idx];
      st.home = parseInt(home.score||'0',10); st.away = parseInt(away.score||'0',10);
      st.status = status; st.score = `${st.away}-${st.home}`; st.period = game.status && game.status.period ? game.status.period : st.period; st.clock = game.status && game.status.displayClock ? game.status.displayClock : (st.clock||''); st.meta = { home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} };
      if(status==='STATUS_FINAL'){
        const cover = determineCoverSpread(st.home, st.away, g.lineHome);
        let coveredSide;
        if(cover==='HOME') coveredSide = canonicalTeamName(g.homeAbbr || g.home);
        else if(cover==='AWAY') coveredSide = canonicalTeamName(g.awayAbbr || g.away);
        else coveredSide = 'PUSH';
        coveredPicks['Sun'][idx] = coveredSide;
      }
    } catch(err){ console.warn('Sunday NFL fetch failed', g.eventId, err); }
  });
  await Promise.all(promises);
  recalcPoints('Sun'); recalcTotal(); updateLeaderboard(); if(picksDay==='Sun') renderPicksTable('Sun'); updateScoreboard();
}

async function updateMondayGames(){
  if(typeof mondayGames==='undefined') return;
  const promises = mondayGames.map(async (g, idx)=>{
    if(!g.eventId) return; // NFL
    try {
      const resp = await fetch(`https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=${g.eventId}`);
      if(!resp.ok) throw new Error('HTTP '+resp.status);
      const data = await resp.json();
      const game = data.header.competitions[0];
      const status = game.status.type.name;
      const home = game.competitors.find(c=>c.homeAway==='home');
      const away = game.competitors.find(c=>c.homeAway==='away');
      const st = mondayStates[idx];
      st.home = parseInt(home.score||'0',10); st.away = parseInt(away.score||'0',10);
      st.status = status; st.score = `${st.away}-${st.home}`; st.period = game.status && game.status.period ? game.status.period : st.period; st.clock = game.status && game.status.displayClock ? game.status.displayClock : (st.clock||''); st.meta = { home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} };
      if(status==='STATUS_FINAL'){
        const cover = determineCoverSpread(st.home, st.away, g.lineHome);
        const spreadIdx = idx===0 ? 0 : 2; // spread pick positions (0,2)
        const ouIdx = idx===0 ? 1 : 3;    // O/U pick positions (1,3)
        let coveredSide;
        if(cover==='HOME') coveredSide = canonicalTeamName(g.homeAbbr || g.home);
        else if(cover==='AWAY') coveredSide = canonicalTeamName(g.awayAbbr || g.away);
        else coveredSide = 'PUSH';
        coveredPicks['Mon'][spreadIdx] = coveredSide;
        // Total resolution
        if(g.total){
          const totalPts = st.home + st.away;
          if(totalPts > g.total) coveredPicks['Mon'][ouIdx] = 'Over';
          else if(totalPts < g.total) coveredPicks['Mon'][ouIdx] = 'Under';
          else coveredPicks['Mon'][ouIdx] = 'PUSH';
        }
        if(window.DEBUG_SPREAD){
          console.log('[MondayFinal]', idx, g.awayAbbr,'@',g.homeAbbr,'lineHome=',g.lineHome,'score',st.home,'-',st.away,'=> cover=',cover,'stored=',coveredPicks['Mon'][spreadIdx]);
        }
      }
    } catch(err){ console.warn('Monday NFL fetch failed', g.eventId, err); }
  });
  await Promise.all(promises); recalcPoints('Mon'); recalcTotal(); updateLeaderboard(); if(picksDay==='Mon') renderPicksTable('Mon'); updateScoreboard();
}

/* ============= Utility / Resolution ============= */
async function resolveSaturdayEventIds(){
  const unresolvedIdx = saturdayGames.reduce((acc,g,i)=>{ if(!g.eventId) acc.push(i); return acc; }, []); if(!unresolvedIdx.length) return;
  try { const resp = await fetch('https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates=20250913'); if(!resp.ok) throw new Error('HTTP '+resp.status); const data = await resp.json(); const events = data.events || []; function cleanName(name){ return (name||'').replace(/#\d+\s*/g,'').replace(/\./g,'').toLowerCase(); }
    events.forEach(ev=>{ const comp = ev.competitions && ev.competitions[0]; if(!comp) return; const competitors = comp.competitors || []; const teams = competitors.map(c=>({ raw:c.team && c.team.displayName, abbr:c.team && c.team.abbreviation })); const cleaned = teams.map(t=>({ ...t, clean: cleanName(t.raw) })); unresolvedIdx.forEach(idx=>{ const g = saturdayGames[idx]; if(g.eventId) return; const awayClean = cleanName(g.away.replace(/#\d+\s*/g,'')); const homeClean = cleanName(g.home.replace(/#\d+\s*/g,'')); const hasAway = cleaned.some(t=> t.clean.includes(awayClean) || awayClean.includes(t.clean) || (g.awayAbbr && t.abbr===g.awayAbbr)); const hasHome = cleaned.some(t=> t.clean.includes(homeClean) || homeClean.includes(t.clean) || (g.homeAbbr && t.abbr===g.homeAbbr)); if(hasAway && hasHome){ g.eventId = ev.id; console.log('[WhatIf] Resolved Saturday eventId', idx, g.away, '@', g.home, '->', g.eventId); } }); });
  } catch(err){ console.warn('Failed to resolve Saturday event IDs', err); }
}

/* ============= Chart Height & Reveal ============= */
function adjustChartHeight(){ const canvas = document.getElementById('leaderboardChart'); const isMobile = innerWidth < 680; const per = isMobile ? 34 : 30; const base = isMobile ? 80 : 100; canvas.style.height = (users.length * per + base) + 'px'; if(chart) chart.resize(); }
let leaderboardShown = false; function maybeRevealLeaderboard(){ if(leaderboardShown) return; const DAY_KEYS=['Thu','Fri','Sat','Sun','Mon']; // Allow legacy 'Thurs' fallback
  if(window.coveredPicks && window.coveredPicks.Thurs && !window.coveredPicks.Thu){ window.coveredPicks.Thu = window.coveredPicks.Thurs; }
  if(DAY_KEYS.some(d=> coveredPicks[d] && coveredPicks[d].some(c=>c!==null))){ document.getElementById('chartWrapper').style.display='block'; leaderboardShown = true; document.body.classList.remove('focus-phase'); document.body.classList.add('post-phase'); adjustChartHeight(); updateLeaderboard(); setTimeout(()=>{ document.getElementById('leaderboardChart').classList.add('winner-glow'); }, 150); } }
window.addEventListener('resize', ()=>{ if(leaderboardShown){ adjustChartHeight(); updateLeaderboard(); } });

/* ============= Picks Toggle ============= */
// Default visible day (will set proper initial on load later).
let picksDay='Sat';
(function initDayToggle(){
  const host=document.getElementById('dayToggleBar'); if(!host) return;
  // Full range of days reinstated.
  const order=['Thu','Fri','Sat','Sun','Mon'];
  function btn(day){ return `<button data-day="${day}" class="picks-btn ${day===picksDay?'active':''}">${day}</button>`; }
  function render(){ host.innerHTML = order.map(btn).join(''); }
  // Expose for later refresh after initialDay is chosen on load
  window.__renderDayToggle = render;
  host.addEventListener('click', e=>{
    const b=e.target.closest('button[data-day]'); if(!b) return;
    const sel=b.getAttribute('data-day');
    if(sel===picksDay) return;
    picksDay=sel; scoreboardDay=sel;
    render();
    updateLeaderboard();
    renderPicksTable(picksDay);
    updateScoreboard();
  });
  render();
})();

/* What-If Simulator removed */

/* ============= Probability Helpers (light heuristics) ============= */
function estimateCoverProbability(gameObj, state){ const line = gameObj.lineHome; const home = state.home, away = state.away; const diff = home - away; let remainingFrac = 1; if(state.status && state.status.startsWith('STATUS_IN')) remainingFrac = 0.5; else if(state.status==='STATUS_FINAL') remainingFrac = 0; const marginNeeded = Math.abs(line); let coverEdge; if(line<0){ coverEdge = (diff - marginNeeded); } else { coverEdge = ((-diff) - marginNeeded); } const adjustedEdge = coverEdge / Math.max(1, marginNeeded); const timeWeight = 3 * (1 - remainingFrac) + 1; const x = adjustedEdge * timeWeight; const pCoverFav = 1 / (1 + Math.exp(-x)); return line<0 ? { homeCover:pCoverFav, awayCover:1-pCoverFav } : { awayCover:pCoverFav, homeCover:1-pCoverFav }; }
function estimateTotalProbability(gameObj, state){ const totalLine = gameObj.total || 0; if(!totalLine) return { over:0.5, under:0.5 }; const scored = state.home + state.away; let remainingFrac = 1; if(state.status && state.status.startsWith('STATUS_IN')) remainingFrac = 0.5; if(state.status==='STATUS_FINAL') remainingFrac = 0; const projected = scored + (scored * (remainingFrac)); const diff = projected - totalLine; const x = diff / (totalLine*0.25 + 1); const pOver = 1/(1+Math.exp(-x)); return { over:pOver, under:1-pOver }; }

function ensureBallSpot(driveObj, data){ if(!driveObj) return; if(driveObj.current && typeof driveObj.current.yardLine==='number') return; try { const cur = data.drives && data.drives.current; if(cur && cur.plays && cur.plays.length){ const lp = cur.plays[cur.plays.length-1]; const end = lp && lp.end ? lp.end : (lp && lp.start ? lp.start : null); if(end && typeof end.yardLine==='number'){ driveObj.current = { yardLine:end.yardLine, team:end.team || (cur.team) }; return; } } if(data.drives && data.drives.previous && data.drives.previous.length){ const prev = data.drives.previous[data.drives.previous.length-1]; if(prev && prev.end && typeof prev.end.yardLine==='number'){ driveObj.current = { yardLine:prev.end.yardLine, team: prev.end.team || prev.team }; } } } catch(e){} }

/* ============= Init on Load ============= */
window.addEventListener('load', async () => {
  document.body.classList.remove('focus-phase'); document.body.classList.add('post-phase');
  // Determine today's relevant day (prioritize Sun if today is Sunday)
  const now = new Date();
  const dow = now.getDay(); // 0=Sun, 1=Mon
  // Original selection logic restored so users land on relevant active day.
  // Automatic day-of-week selection (0=Sun..6=Sat)
  let initialDay = 'Sat';
  if(dow===0) initialDay='Sun';
  else if(dow===1) initialDay='Mon';
  else if(dow===4) initialDay='Thu';
  else if(dow===5) initialDay='Fri';
  else if(dow===6) initialDay='Sat'; // explicit for clarity
  // Normalize any legacy 'Thurs' keys to 'Thu' before initial calculations
  if(window.picksLabels && window.picksLabels.Thurs && !window.picksLabels.Thu){ window.picksLabels.Thu = window.picksLabels.Thurs; }
  if(window.userPicks && window.userPicks.Thurs && !window.userPicks.Thu){ window.userPicks.Thu = window.userPicks.Thurs; }
  if(window.coveredPicks && window.coveredPicks.Thurs && !window.coveredPicks.Thu){ window.coveredPicks.Thu = window.coveredPicks.Thurs; }
  recalcPoints('Thu'); recalcPoints('Fri'); recalcPoints('Sat'); recalcPoints('Sun'); recalcPoints('Mon'); recalcTotal(); updateLeaderboard();
  // Enable live leaderboard by default
  LIVE_LEADERBOARD_ENABLED = true;
  const liveCbInit = document.getElementById('liveLbCheckbox');
  if(liveCbInit){ liveCbInit.checked = true; }
  const noteInit = document.getElementById('liveProjNote'); if(noteInit) noteInit.style.display='inline';
  updateLeaderboard();
  picksDay=initialDay; scoreboardDay=initialDay; if(window.__renderDayToggle) window.__renderDayToggle(); renderPicksTable(picksDay); const stEl=document.getElementById('scoresTitle'); if(stEl) stEl.textContent='Scores ('+initialDay+')';
  if(typeof window==='undefined' || window.LIVE_FETCH_ENABLED!==false){
    await Promise.all([
      updateNFLGame().catch(e=>console.warn('NFL init fetch failed', e)),
      updateCollegeGame().catch(e=>console.warn('CFB Thurs init fetch failed', e)),
      updateFridayGames().catch(e=>console.warn('Friday init fetch failed', e)),
      (async()=>{ await resolveSaturdayEventIds(); await updateSaturdayGames(); })().catch(e=>console.warn('Saturday init fetch failed', e)),
      updateSundayGames().catch(e=>console.warn('Sunday init fetch failed', e)),
      updateMondayGames().catch(e=>console.warn('Monday init fetch failed', e))
    ]);
  } else {
    console.log('[Init] LIVE_FETCH_ENABLED=false; skipping initial fetches/ingest');
  }
  updateScoreboard(); setTimeout(()=>{ document.getElementById('leaderboardChart').classList.add('winner-glow'); },150);
  // Removed periodic forced update that previously animated gradient title (no longer needed)
  // Disabled periodic live polling (was every 45s) to reduce network noise per updated requirements.
  // If re-enabled, wrap behind a feature flag.
  // Throttled polling: 60s cadence to reduce load / avoid rate limits
  // Live polling disabled (all games finalized). Re-enable by uncommenting block below.
  /*
  setInterval(()=>{
    if(fridayStates.some(s=>s.status && s.status!=='STATUS_FINAL' && s.status!=='STATUS_SCHEDULED')) updateFridayGames();
    if(saturdayStates.some(s=>s.status && s.status!=='STATUS_FINAL' && s.status!=='STATUS_SCHEDULED')) updateSaturdayGames();
    if(sundayStates.some(s=>s.status && s.status!=='STATUS_FINAL' && s.status!=='STATUS_SCHEDULED')) updateSundayGames();
    if(mondayStates.some(s=>s.status && s.status!=='STATUS_FINAL' && s.status!=='STATUS_SCHEDULED')) updateMondayGames();
    updateScoreboard();
  }, 60000);
  */
  if(typeof window==='undefined' || window.LIVE_FETCH_ENABLED!==false){ setTimeout(()=>{ resolveSaturdayEventIds().then(updateSaturdayGames); }, 20000); }
  // Simulator initialization removed

  // Collapse button logic
  const collapseBtn = document.getElementById('picksCollapseBtn');
  if(collapseBtn){
    collapseBtn.addEventListener('click', () => {
      const expanded = collapseBtn.getAttribute('aria-expanded') === 'true';
      if(expanded){
        document.body.classList.add('picks-collapsed');
        collapseBtn.setAttribute('aria-expanded','false');
        collapseBtn.textContent='Show Picks';
      } else {
        document.body.classList.remove('picks-collapsed');
        collapseBtn.setAttribute('aria-expanded','true');
        collapseBtn.textContent='Hide Picks';
      }
    });
  }

  // Live leaderboard toggle removed; always leave projections enabled. Note element kept hidden if absent.
});
