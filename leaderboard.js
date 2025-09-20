/* Core logic extracted from leaderboard.html */

// Static final results for past days (used when those days are complete or when
// dynamic game objects are not present/loaded). This guarantees a scoreboard
// row with actual final scores instead of a blank table.
// NOTE: Thursday NFL: Miami @ Buffalo final 21-31 (BUF wins, MIA covers +11.5, total 52 > 50.5 => Over)
// Friday CFB finals: Tulsa @ Oklahoma State 19-12 (Tulsa wins & covers), Iowa @ Rutgers 38-28 (Iowa wins & covers)
// Lines/totals for Friday not provided -> leave null so we render blanks.
const finalResults = {
  'Thurs': [
    { awayAbbr:'MIA', homeAbbr:'BUF', awayScore:21, homeScore:31, lineHome:-11.5, total:50.5 }
  ],
  'Fri': [
    { awayAbbr:'TLSA', homeAbbr:'OKST', awayScore:19, homeScore:12, lineHome:null, total:null },
    { awayAbbr:'IOWA', homeAbbr:'RUT', awayScore:38, homeScore:28, lineHome:null, total:null }
  ]
};

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
// Normalize existing Saturday covered picks
// NOTE: Week 4 Thursday picks are static & locked (see config.js userPicks['Thurs']).
coveredPicks['Sat'] = coveredPicks['Sat'].map(c=> (c && c!=='PUSH') ? canonicalTeamName(c) : c);

function recalcPoints(day){
  if(!picksLabels[day]) return;
  users.forEach(u=>{
    const picks = userPicks[day] && userPicks[day][u.username];
    let pts=0; if(picks){ (coveredPicks[day]||[]).forEach((cov,i)=>{ if(!cov || cov==='PUSH') return; if(picks[i]===cov) pts++; }); }
    if(day==='Thurs') u.thurs = pts; else if(day==='Fri') u.fri = pts; else if(day==='Sat') u.sat = pts; else if(day==='Sun') u.sun = pts; else if(day==='Mon') u.mon = pts;
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
  try { recalcPoints('Thurs'); recalcPoints('Fri'); recalcPoints('Sat'); recalcPoints('Sun'); recalcTotal(); } catch(e) { /* silent */ }

  function pointsForDay(day, user){
    const picks = (userPicks[day] && userPicks[day][user.username]) || [];
    const covers = coveredPicks[day] || [];
    function norm(raw){
      if(raw==null) return '';
      let s = canonicalTeamName(raw.toString());
      s = s.toLowerCase();
      s = s.replace(/[#.']/g,'');
      s = s.replace(/\bst\b/g,'st');
      s = s.replace(/kansas st/g,'kansas state');
      s = s.replace(/wv?u/g,'west virginia');
      s = s.replace(/pittsburg?h?/g,'pittsburgh');
      s = s.replace(/ga tech|georgia tech/g,'georgia tech');
      s = s.replace(/south fla|s florida/g,'south florida');
      s = s.replace(/texas a ?&?m|texas am/g,'texas a&m');
      s = s.replace(/nd$/,'notre dame');
      s = s.replace(/ala\b/g,'alabama');
      s = s.replace(/sc ?ar|s ?car|south car\b/g,'south carolina');
      s = s.replace(/miami(?![a-z])/,'miami');
      s = s.replace(/ +/g,' ').trim();
      return s;
    }
    let pts=0;
    covers.forEach((c,i)=>{
      if(!c || c==='PUSH') return;
      const pick = picks[i];
      if(!pick) return;
      if((c==='Over' || c==='Under') && pick===c){ pts++; return; }
      if(norm(pick) === norm(c)) pts++;
      else if(window.DEBUG_POINTS_NORM){ console.log('[Mismatch]', day, user.username, 'pick=', pick, 'cover=', c, 'normPick=', norm(pick), 'normCover=', norm(c)); }
    });
    return pts;
  }

  // Compute actual day values (pre-sort)
  const thursActual = users.map(u=> pointsForDay('Thurs', u));
  const friActual   = users.map(u=> pointsForDay('Fri', u));
  const satActual   = users.map(u=> pointsForDay('Sat', u));
  const sunActual   = users.map(u=> pointsForDay('Sun', u));
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
    u.sat   = satActual[i];
    u.sun   = sunActual[i];
    u.mon   = monActual[i];
    u.total = thursActual[i] + friActual[i] + satActual[i] + sunActual[i] + monActual[i];
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
    { label:'Sun', data: sunVals, backgroundColor:DAY_COLORS.Sun.fill, borderColor:'#ffffff', borderWidth:1, barThickness, borderRadius:4, borderSkipped:false, stack:'points' },
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
  // Update explanatory note text (toggle already controls visibility)
  const noteEl = document.getElementById('liveProjNote'); if(noteEl) noteEl.remove();

  // Update legend for Live* dataset
  // Removed Live* legend chip logic.
}

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
  if(day==='Thurs'){
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
  if(day==='Thurs'){
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

function renderPicksTable(day=currentDay){
  // Requirement update: show scheduled games for Sat-Sun-Mon again (no kickoff-based hiding). Always render all defined columns for selected day.
  const tbl = document.getElementById('picksTable');
  let labelCount = (picksLabels[day]||[]).length;
  if(day==='Sun'){
    // Preserve earlier dynamic expansion in case server adds more Sunday picks than initial labels length.
    const maxUserLen = Object.values(userPicks['Sun']||{}).reduce((m,arr)=> Math.max(m, Array.isArray(arr)?arr.length:0), 0);
    if(maxUserLen > labelCount) labelCount = maxUserLen;
  }
  function statusFor(day, idx){
    if(day==='Thurs'){
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
      let rawPick = picks[i] || '-';
      const displayPick = lookupAbbr(rawPick);
  const cov = coveredPicks[day][i];
  let cls='';
  if(cov){
    const normPick = (rawPick||'').toString().trim().toLowerCase();
    const normCov = cov.toString().trim().toLowerCase();
    if(cov==='PUSH') cls='push';
    else if(normPick && normCov && normPick === normCov) cls='hit';
    else if(normPick && normCov && normPick !== normCov) cls='miss';
  }
      // Live covering effect (only if not final yet and no hit/miss assigned)
        if(!cov){
          // Determine if this column represents a total (Over/Under) where we suppress live shading
          const isTotalCol = (
            (day==='Thurs' && i===1) || // Thursday NFL total
            (day==='Mon' && (i===1 || i===3)) // Monday totals TB/HOU & LAC/LVR
          );
          if(!isTotalCol){
            const info = liveGameCoverInfo(day,i);
            if(info && info.coverAbbr){
              const pct = Math.round(info.progress*100);
              if(info.coverAbbr === displayPick){
                return `<td class="${cls} picks-cell-live covering" style="--fill:${pct}%">${displayPick}</td>`;
              } else if(rawPick && rawPick !== '-') {
                return `<td class="${cls} picks-cell-live trailing" style="--fill:${pct}%">${displayPick}</td>`;
              }
            }
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
  if(!scoreboardDay){
    const now = new Date();
    const dow = now.getDay(); // 0=Sun..6=Sat
    if(dow===0) scoreboardDay='Sun';
    else if(dow===1) scoreboardDay='Mon';
    else if(dow===4) scoreboardDay='Thurs';
    else if(dow===5) scoreboardDay='Fri';
    else if(dow===6) scoreboardDay='Sat';
    else scoreboardDay='Sat'; // Tue/Wed default to upcoming Saturday slate
  }
  const meta = (day)=> day==='Fri'? { games:fridayGames, states:fridayStates, times:fridayStartTimes } :
    day==='Sat'? { games:saturdayGames, states:saturdayStates, times:saturdayStartTimes } :
    day==='Sun'? { games:sundayGames, states:sundayStates, times:sundayStartTimes } :
    day==='Mon'? { games:mondayGames, states:mondayStates, times:mondayStartTimes } : { games:[], states:[], times:[] };
  const { games, states, times } = meta(scoreboardDay);

  // If past completed day (Thurs/Fri) and we have static final results, render those (preferred over labels fallback)
  if((scoreboardDay==='Thurs' || scoreboardDay==='Fri') && (!games || !games.length) && finalResults[scoreboardDay]){
    console.log('[Scoreboard] Using static finals for', scoreboardDay, 'games length=', games?games.length:0);
    const header = '<tr><th>Game</th><th>Final Score</th><th>Spread</th><th>Total</th></tr>';
    const rows = finalResults[scoreboardDay].map(fr=>{
      const scoreFrag = `${fr.awayScore}-${fr.homeScore}`;
      let spreadTxt='';
      if(typeof fr.lineHome === 'number'){
        const fav = fr.lineHome < 0 ? fr.homeAbbr : fr.awayAbbr;
        spreadTxt = `${fav} -${Math.abs(fr.lineHome)}`;
      }
      let totalTxt = fr.total? `O/U ${fr.total}`: '';
      return `<tr class="final-row"><td><span class="game-label">${fr.awayAbbr} @ ${fr.homeAbbr}</span></td><td>${scoreFrag} <span class="detail">FINAL</span></td><td>${spreadTxt}</td><td>${totalTxt}</td></tr>`;
    }).join('');
    tbl.innerHTML = header + rows;
    const titleEl = document.getElementById('scoresTitle'); if(titleEl) titleEl.textContent = 'Scores ('+scoreboardDay+')';
    return;
  }
  function spreadLabel(g){ const ln=g.lineHome; if(typeof ln!=='number') return ''; if(ln===0) return 'PK'; const fav = ln<0? g.homeAbbr : g.awayAbbr; return `${fav} -${Math.abs(ln)}`; }
  function totalLabel(g){ return g.total ? `O/U ${g.total}` : ''; }
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
  const header = '<tr><th>Game</th><th>Score / Status</th><th>Spread</th><th>Total</th></tr>';
  const rows = games.map((g,i)=>{
    if(!games.length){ console.log('[Scoreboard] No games array for day', scoreboardDay); }
    const st = states && states[i] ? states[i] : null; if(st) st._idx = i; // attach index for statusDetail time lookup
    const live = st && st.status && st.status !== 'STATUS_SCHEDULED';
    const scoreFrag = live ? `${st.away}-${st.home}` : (times && times[i] ? times[i] : '');
    const detail = statusDetail(st);
    const spread = spreadLabel(g);
    const total = totalLabel(g);
    const rowCls = st? rowClass(st.status): '';
    return `<tr class="${rowCls}"><td><span class="game-label">${g.awayAbbr} @ ${g.homeAbbr}</span></td><td>${scoreFrag}${detail? ' <span class="detail">'+detail+'</span>':''}</td><td>${spread}</td><td>${total}</td></tr>`;
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
      if(spreadCover==='HOME') coveredPicks['Thurs'][0] = 'GB'; else if(spreadCover==='AWAY') coveredPicks['Thurs'][0] = 'WASH'; else coveredPicks['Thurs'][0] = 'PUSH';
      const totalPts = parseInt(home.score,10)+parseInt(away.score,10);
      if(totalPts > nflGame.total) coveredPicks['Thurs'][1] = 'Over'; else if(totalPts < nflGame.total) coveredPicks['Thurs'][1] = 'Under'; else coveredPicks['Thurs'][1] = 'PUSH';
      recalcPoints('Thurs'); recalcTotal(); updateLeaderboard(); renderPicksTable(picksDay);
    }
    updateScoreboard();
  } catch(err){ console.warn('Failed NFL fetch', err); }
}

async function updateCollegeGame(){
  try { const resp = await fetch(`https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=${collegeGame.eventId}`); if(!resp.ok) throw new Error('HTTP '+resp.status); const data = await resp.json();
    const game = data.header.competitions[0]; const status = game.status.type.name; const home = game.competitors.find(c=>c.homeAway==='home'); const away = game.competitors.find(c=>c.homeAway==='away');
    if(data.drives && data.drives.current){ const d = data.drives.current; collegeState.drive = { possession: d.team && d.team.id, downDistanceText: d.displayResult ? null : d.shortDisplayResult, shortDownDistanceText: d.shortDownDistanceText || d.downDistanceText, yardsToEndzone: d.yardsToEndzone, start: d.start && { yardLine: d.start.yardLine, team: d.start.team }, current: d.end && { yardLine: d.end.yardLine, team: d.end.team }, clock: game.status && game.status.displayClock ? { displayValue: game.status.displayClock } : null, isRedZone: d.isRedZone, teamIds: { [away.team.id]: away.team.id, [home.team.id]: home.team.id }, homeTeamId: home.team.id, awayTeamId: away.team.id, plays: d.plays && d.plays.length ? d.plays.length : d.playCount, yards: d.yards, timeElapsed: d.timeElapsed || (d.start && d.end && d.end.clock && d.end.clock.displayValue), yardsToGo: d.yardsToGo || d.distance }; ensureBallSpot(collegeState.drive, data); } else { collegeState.drive = null; }
    const oldAway = collegeState.away, oldHome = collegeState.home; collegeState.away = parseInt(away.score||'0',10); collegeState.home = parseInt(home.score||'0',10); collegeState.score = `${collegeState.away}-${collegeState.home}`; collegeState.status = status; const coverProb = estimateCoverProbability(collegeGame, collegeState); const totalProb = estimateTotalProbability(collegeGame, collegeState); collegeState.period = game.status && game.status.period ? game.status.period : collegeState.period;
    function mapColorCFB(abbr){ const m={NCSU:'#CC0000',WF:'#9E7E38'}; return m[abbr]||'#ff8800'; }
    collegeState.meta = { coverProb, totalProb, favored: collegeGame.lineHome<0? 'HOME':'AWAY', home:{abbr:collegeGame.homeAbbr}, away:{abbr:collegeGame.awayAbbr}, homeColor:mapColorCFB(collegeGame.homeAbbr), awayColor:mapColorCFB(collegeGame.awayAbbr) };
    if(status === 'STATUS_FINAL'){
      const cover = determineCoverSpread(parseInt(home.score,10), parseInt(away.score,10), collegeGame.lineHome);
      if(cover==='HOME') coveredPicks['Thurs'][2] = 'WF'; else if(cover==='AWAY') coveredPicks['Thurs'][2] = 'NCSU'; else coveredPicks['Thurs'][2] = 'PUSH';
      recalcPoints('Thurs'); recalcTotal(); updateLeaderboard(); renderPicksTable(picksDay);
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
let leaderboardShown = false; function maybeRevealLeaderboard(){ if(leaderboardShown) return; if(['Thurs','Fri','Sat','Sun','Mon'].some(d=> coveredPicks[d] && coveredPicks[d].some(c=>c!==null))){ document.getElementById('chartWrapper').style.display='block'; leaderboardShown = true; document.body.classList.remove('focus-phase'); document.body.classList.add('post-phase'); adjustChartHeight(); updateLeaderboard(); setTimeout(()=>{ document.getElementById('leaderboardChart').classList.add('winner-glow'); }, 150); } }
window.addEventListener('resize', ()=>{ if(leaderboardShown){ adjustChartHeight(); updateLeaderboard(); } });

/* ============= Picks Toggle ============= */
// Default visible day (will set proper initial on load later).
let picksDay='Sat';
(function initDayToggle(){
  const host=document.getElementById('dayToggleBar'); if(!host) return;
  // Full range of days reinstated.
  const order=['Thurs','Fri','Sat','Sun','Mon'];
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
  let initialDay = 'Sat';
  if(dow===0) initialDay='Sun';
  else if(dow===1) initialDay='Mon';
  else if(dow===5) initialDay='Fri';
  else if(dow===4) initialDay='Thurs';
  recalcPoints('Thurs'); recalcPoints('Fri'); recalcPoints('Sat'); recalcPoints('Sun'); recalcPoints('Mon'); recalcTotal(); updateLeaderboard();
  // Enable live leaderboard by default
  LIVE_LEADERBOARD_ENABLED = true;
  const liveCbInit = document.getElementById('liveLbCheckbox');
  if(liveCbInit){ liveCbInit.checked = true; }
  const noteInit = document.getElementById('liveProjNote'); if(noteInit) noteInit.style.display='inline';
  updateLeaderboard();
  picksDay=initialDay; scoreboardDay=initialDay; if(window.__renderDayToggle) window.__renderDayToggle(); renderPicksTable(picksDay); const stEl=document.getElementById('scoresTitle'); if(stEl) stEl.textContent='Scores ('+initialDay+')';
  await Promise.all([
    updateNFLGame().catch(e=>console.warn('NFL init fetch failed', e)),
    updateCollegeGame().catch(e=>console.warn('CFB Thurs init fetch failed', e)),
    updateFridayGames().catch(e=>console.warn('Friday init fetch failed', e)),
    (async()=>{ await resolveSaturdayEventIds(); await updateSaturdayGames(); })().catch(e=>console.warn('Saturday init fetch failed', e)),
  updateSundayGames().catch(e=>console.warn('Sunday init fetch failed', e)),
  updateMondayGames().catch(e=>console.warn('Monday init fetch failed', e)),
    (async()=>{
      // Ingest Sunday picks from server if available; structure: { email: { picks: [...], ts } }
      try {
        const resp = await fetch('/picks/sunday/public');
        if(resp.ok){
          const data = await resp.json();
          Object.keys(data).forEach(email=>{
            const entry = data[email];
            if(!entry || !Array.isArray(entry.picks)) return;
            let picksArr = entry.picks.map(p=> normalizeNFLAbbr(p || ''));
            // Pad / trim to exactly 9
            if(picksArr.length < (picksLabels['Sun']||[]).length){
              picksArr = picksArr.concat(Array((picksLabels['Sun']||[]).length - picksArr.length).fill(''));
            } else if(picksArr.length > (picksLabels['Sun']||[]).length){
              picksArr = picksArr.slice(0,(picksLabels['Sun']||[]).length);
            }
            userPicks['Sun'][email] = picksArr; // always overwrite to keep freshest
          });
          // NOTE: Future (not-started) games remain hidden in table by gating logic above; when kickoff passes renderPicksTable will expose those columns.
          const loadedCount = Object.keys(data).length;
          if(loadedCount===0){ console.warn('[SundayIngest] /picks/sunday/public returned 0 entries'); }
          recalcPoints('Sun'); recalcTotal(); updateLeaderboard(); if(picksDay==='Sun') renderPicksTable('Sun');
        } else {
          console.warn('[SundayIngest] public endpoint status', resp.status);
        }
      } catch(err){ console.warn('Failed to ingest Sunday picks', err); }
      // Fallback: if still no picks loaded, attempt static JSON file (Flask writes data/sunday_picks.json)
      try {
        if(Object.keys(userPicks['Sun']||{}).length===0){
          const alt = await fetch('/data/sunday_picks.json');
          if(alt.ok){
            const list = await alt.json();
            if(Array.isArray(list)){
              list.forEach(rec=>{
                if(!rec || !rec.email || !Array.isArray(rec.picks)) return;
                let arr = rec.picks.map(p=> normalizeNFLAbbr(p||''));
                if(arr.length < (picksLabels['Sun']||[]).length){ arr = arr.concat(Array((picksLabels['Sun']||[]).length-arr.length).fill('')); }
                userPicks['Sun'][rec.email] = arr;
              });
              console.log('[SundayIngest] Loaded fallback static sunday_picks.json');
              recalcPoints('Sun'); recalcTotal(); updateLeaderboard(); if(picksDay==='Sun') renderPicksTable('Sun');
            }
          }
        }
      } catch(e){ console.warn('Fallback sunday_picks.json fetch failed', e); }
    })(),
    updateMondayGames().catch(e=>console.warn('Monday init fetch failed', e)),
    (async()=>{
      // Ingest official Monday picks from CSV-backed endpoint
      try {
        const resp = await fetch('/picks/monday/official');
        if(resp.ok){
          const payload = await resp.json();
          const entries = (payload && payload.entries) || {};
          Object.keys(entries).forEach(email=>{
            const entry = entries[email];
            if(!entry || !Array.isArray(entry.picks)) return;
            let arr = entry.picks.map(p=> p || '');
            // Normalize Over/Under case and team abbreviations
            arr = arr.map(v=> v==='OVER'?'Over': v==='UNDER'?'Under': normalizeNFLAbbr(v));
            // Pad/trim to exactly 4 Monday picks
            if(arr.length < (picksLabels['Mon']||[]).length){
              arr = arr.concat(Array((picksLabels['Mon']||[]).length - arr.length).fill(''));
            } else if(arr.length > (picksLabels['Mon']||[]).length){
              arr = arr.slice(0,(picksLabels['Mon']||[]).length);
            }
            userPicks['Mon'][email] = arr;
          });
          // Ensure Nick (finsmaniac...) present even if NA provided server-side fallback (mirrors server logic)
          if(!userPicks['Mon']['finsmaniac1551@gmail.com']){
            userPicks['Mon']['finsmaniac1551@gmail.com'] = Array((picksLabels['Mon']||[]).length).fill('');
          }
          recalcPoints('Mon'); recalcTotal(); updateLeaderboard(); if(picksDay==='Mon') renderPicksTable('Mon');
        } else {
          console.warn('[MondayIngest] official endpoint status', resp.status);
        }
      } catch(err){ console.warn('Failed to ingest Monday official picks', err); }
      // Client-side fallback: directly parse raw CSV if user picks still missing or partially empty
      try {
        const needed = (picksLabels['Mon']||[]).length;
        // Determine completeness: every known user has an array of length 4 with at least one non-empty value
        const allUserEmails = (window._lbConfig && Array.isArray(window._lbConfig.users)? window._lbConfig.users.map(u=>u.username): (users||[]).map(u=>u.username));
        const mondayMap = userPicks['Mon'] || {};
        const missing = allUserEmails.some(em=> !Array.isArray(mondayMap[em]) || mondayMap[em].length!==needed || mondayMap[em].every(v=>!v));
        if(missing){
          const csvResp = await fetch('/09_15_Picks.csv');
          if(csvResp.ok){
            const text = await csvResp.text();
            const lines = text.split(/\r?\n/).filter(l=>l.trim().length>0);
            if(lines.length>1){
              const rawHeader = lines[0];
              // Split preserving commas inside quotes (not expected here, but future-proof lightly)
              const headerParts = rawHeader.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/).map(h=>h.replace(/"/g,'').trim());
              const lower = headerParts.map(h=>h.toLowerCase());
              const emailIdx = lower.findIndex(h=> h.includes('username') || h.includes('email'));
              // Flexible detection: first column referencing TB & HOU & spread; second referencing O/U (TB/HOU); third referencing LAC & LVR; fourth O/U for LAC/LVR
              function colMatch(fn){ return lower.findIndex(fn); }
              const col1 = colMatch(h=> h.includes('tb') && h.includes('hou') && (h.includes('+') || h.includes('-') || h.includes('@')) && !h.includes('o/u')); // spread TB @ HOU
              const col2 = colMatch(h=> h.includes('tb') && h.includes('hou') && (h.includes('o/u') || h.includes('over'))); // total TB/HOU
              const col3 = colMatch(h=> h.includes('lac') && (h.includes('lvr') || h.includes('lv')) && !h.includes('o/u') && (h.includes('+') || h.includes('-') || h.includes('@'))); // spread LAC @ LVR
              const col4 = colMatch(h=> h.includes('lac') && (h.includes('lvr') || h.includes('lv')) && (h.includes('o/u') || h.includes('over'))); // total LAC/LVR
              const mapCols = [col1,col2,col3,col4];
              if(mapCols.some(i=> i<0)) console.warn('[MondayIngest][Fallback] Some Monday column indices not found', mapCols);
              function normVal(v, idx){
                if(!v) return '';
                const raw = v.replace(/"/g,'').trim();
                if(!raw) return '';
                if(/^over$/i.test(raw)) return 'Over';
                if(/^under$/i.test(raw)) return 'Under';
                // Only allow specific team tokens per column to avoid misalignment
                if(idx===0){ // TB or HOU
                  if(/^tb$/i.test(raw)) return 'TB';
                  if(/^hou$/i.test(raw)) return 'HOU';
                } else if(idx===2){ // LAC or LVR
                  if(/^lac$/i.test(raw)) return 'LAC';
                  if(/^lvr$/i.test(raw) || /^lv$/i.test(raw)) return 'LVR';
                }
                // Fallback: try generic normalization for teams
                return normalizeNFLAbbr(raw);
              }
              for(let li=1; li<lines.length; li++){
                const rawLine = lines[li];
                const parts = rawLine.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/).map(p=>p.replace(/"/g,'').trim());
                if(parts.every(p=>!p)) continue; // skip blank
                const email = (parts[emailIdx]||'').trim().toLowerCase();
                if(!email) continue;
                if(userPicks['Mon'][email] && userPicks['Mon'][email].some(v=>v)) continue; // first occurrence wins
                const arr = mapCols.map((ci, idx)=> ci>=0 && parts[ci] ? normVal(parts[ci], idx) : '');
                userPicks['Mon'][email] = arr;
              }
              // Fix typo email mapping
              if(userPicks['Mon']['hankruddenn@yahoo.com'] && !userPicks['Mon']['hankrudden@yahoo.com']){
                userPicks['Mon']['hankrudden@yahoo.com'] = userPicks['Mon']['hankruddenn@yahoo.com'];
              }
              if(!userPicks['Mon']['finsmaniac1551@gmail.com']){
                userPicks['Mon']['finsmaniac1551@gmail.com'] = Array(needed).fill('');
              }
              recalcPoints('Mon'); recalcTotal(); updateLeaderboard(); if(picksDay==='Mon') renderPicksTable('Mon');
              console.log('[MondayIngest][Fallback] Loaded picks from raw CSV (flex parser)');
            } else {
              console.warn('[MondayIngest][Fallback] CSV had header only');
            }
          } else {
            console.warn('[MondayIngest][Fallback] Could not fetch CSV file:', csvResp.status);
          }
        }
      } catch(csvErr){ console.warn('[MondayIngest][Fallback] CSV parse error', csvErr); }
    })()
  ]);
  updateScoreboard(); setTimeout(()=>{ document.getElementById('leaderboardChart').classList.add('winner-glow'); },150);
  // Removed periodic forced update that previously animated gradient title (no longer needed)
  // Disabled periodic live polling (was every 45s) to reduce network noise per updated requirements.
  // If re-enabled, wrap behind a feature flag.
  // Throttled polling: 60s cadence to reduce load / avoid rate limits
  setInterval(()=>{
    if(fridayStates.some(s=>s.status && s.status!=='STATUS_FINAL' && s.status!=='STATUS_SCHEDULED')) updateFridayGames();
    if(saturdayStates.some(s=>s.status && s.status!=='STATUS_FINAL' && s.status!=='STATUS_SCHEDULED')) updateSaturdayGames();
    if(sundayStates.some(s=>s.status && s.status!=='STATUS_FINAL' && s.status!=='STATUS_SCHEDULED')) updateSundayGames();
    if(mondayStates.some(s=>s.status && s.status!=='STATUS_FINAL' && s.status!=='STATUS_SCHEDULED')) updateMondayGames();
    updateScoreboard();
  }, 60000);
  setTimeout(()=>{ resolveSaturdayEventIds().then(updateSaturdayGames); }, 20000);
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
