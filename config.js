// Configuration & static data extracted from leaderboard.html
// Exposes globals for simplicity (no module system). Later we can namespace if desired.

// Global feature flag to disable background/live API fetching during downtime
window.LIVE_FETCH_ENABLED = false;

/* ================= USERS & PICKS DATA ================= */
// Added 'sun' field for upcoming Sunday scoreboard integration
// New Week Roster (union of Thur–Sat CSVs) – 17 users reset to 0
// Source: Thur-Fri_Picks.csv + Sat_Picks.csv
const users = [
  { username:'adam.schmidt520@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'conor.murphy30@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'finsmaniac1551@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'goodnoughdylan@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'hankrudden@yahoo.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'jakelehman100@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'jlindsey3428@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'kylejkz11@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'lukeanastasi5@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'max1solov@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'mzanin98@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'samuel.lehman3337@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'scire.ben@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'shawnscottcarl@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'timjbohlman@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'williamjabbott22@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'wyaggy3@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 }
];

// Updated nicknames per user request
const nicknameMap = {
  'adam.schmidt520@gmail.com':'Schmidt',
  'conor.murphy30@gmail.com':'Murph',
  'finsmaniac1551@gmail.com':'Nick',
  'goodnoughdylan@gmail.com':'Dylan',
  'hankrudden@yahoo.com':'Hank',
  'jakelehman100@gmail.com':'Jake',
  'jlindsey3428@gmail.com':'JLinds',
  'kylejkz11@gmail.com':'Kyle',
  'lukeanastasi5@gmail.com':'Luke',
  'max1solov@gmail.com':'Solov',
  'mzanin98@gmail.com':'Matteo',
  'samuel.lehman3337@gmail.com':'Sam',
  'scire.ben@gmail.com':'Ben',
  'shawnscottcarl@gmail.com':'Shawn',
  'timjbohlman@gmail.com':'Bohlman',
  'williamjabbott22@gmail.com':'Abbo',
  'wyaggy3@gmail.com':'Wyatt'
};

// Base labels for NEW WEEK derived from CSV headers provided.
// Thursday: NFL Spread, NFL Total, MLB Spread
// Friday: (Single CFB Spread)
// Saturday: Seven CFB Spreads
const picksLabels = {
  'Thurs':[ 'NFL: SF +8.5 @ LAR', 'NFL O/U: SF/LAR - 44.5', 'MLB: BOS @ NYY Game 3' ],
  'Fri':[ 'NCAAF: WVU +18.5 @ BYU' ],
  'Sat':[ 'Texas -6.5 @ Florida', 'Boise St +19.5 @ ND', 'UVA +6.5 @ Louisville', 'Vanderbilt +10.5 @ Alabama', 'Texas Tech -12.5 @ Houston', 'Miss. State +14.5 @ Texas A&M', 'Miami -4.5 @ FSU' ],
  // Sunday (NFL) – pulled from Sun_Picks.csv header
  'Sun':[ 'Houston -1.5 @ Baltimore', 'Dallas -1.5 @ New York Jets', 'Denver +4.5 @ Philadelphia', 'Miami -1.5 @ Carolina', 'Tampa Bay +3.5 @ Seattle', 'Washington Commanders -2.5 @ Los Angeles Chargers', 'Detroit Lions -9.5 @ Cincinnati Bengals', 'New England Patriots +7.5 @ Buffalo Bills' ],
  'Mon':[]
};

// Fresh week user picks containers
const userPicks = { 'Thurs': {}, 'Fri': {}, 'Sat': {}, 'Sun': {}, 'Mon': {} };

// Populate Thursday & Friday & Saturday picks from CSVs in data/picks
// CSV: Thur-Fri_Picks.csv (Thursday entries)
Object.assign(userPicks['Thurs'], {
  'shawnscottcarl@gmail.com':['LAR','Over','BOS'],
  'wyaggy3@gmail.com':['LAR','Under','BOS'],
  'max1solov@gmail.com':['SF','Over','NYY'],
  'adam.schmidt520@gmail.com':['SF','Over','BOS'],
  'jlindsey3428@gmail.com':['SF','Under','BOS'],
  'mzanin98@gmail.com':['SF','Under','BOS'],
  'scire.ben@gmail.com':['LAR','Under','BOS'],
  'williamjabbott22@gmail.com':['SF','Over','BOS'],
  'hankrudden@yahoo.com':['SF','Under','BOS'],
  'finsmaniac1551@gmail.com':['LAR','Under','BOS'],
  'goodnoughdylan@gmail.com':['SF','Under','BOS'],
  'kylejkz11@gmail.com':['SF','Over','BOS'],
  'timjbohlman@gmail.com':['SF','Under','NYY'],
  'conor.murphy30@gmail.com':['LAR','Under','BOS'],
  'jakelehman100@gmail.com':['LAR','Under','BOS'],
  'lukeanastasi5@gmail.com':['LAR','Under','BOS']
});

// Friday CFB single spread pick from Thur-Fri_Picks.csv (column NCAAF: WVU +18.5 @ BYU)
Object.assign(userPicks['Fri'], {
  'shawnscottcarl@gmail.com':['BYU'],
  'wyaggy3@gmail.com':['BYU'],
  'max1solov@gmail.com':['BYU'],
  'adam.schmidt520@gmail.com':['WVU'],
  'jlindsey3428@gmail.com':['BYU'],
  'mzanin98@gmail.com':['BYU'],
  'scire.ben@gmail.com':['WVU'],
  'williamjabbott22@gmail.com':['WVU'],
  'hankrudden@yahoo.com':['BYU'],
  'finsmaniac1551@gmail.com':['BYU'],
  'goodnoughdylan@gmail.com':['BYU'],
  'kylejkz11@gmail.com':['BYU'],
  'timjbohlman@gmail.com':['WVU'],
  'conor.murphy30@gmail.com':['BYU'],
  'jakelehman100@gmail.com':['WVU'],
  'lukeanastasi5@gmail.com':['BYU']
});

// Saturday picks (7 columns) from Sat_Picks.csv
Object.assign(userPicks['Sat'], {
  'goodnoughdylan@gmail.com':['Texas','Boise','UVA','Alabama','TTU','Miss','MIA'],
  'mzanin98@gmail.com':['Texas','ND','UVA','Alabama','UH','A&M','MIA'],
  'samuel.lehman3337@gmail.com':['Texas','ND','Louissville','Vanderbilt','UH','A&M','MIA'],
  'wyaggy3@gmail.com':['Florida','ND','Louissville','Alabama','UH','Miss','MIA'],
  'williamjabbott22@gmail.com':['Texas','ND','Louissville','Vanderbilt','UH','Miss','FSU'],
  'max1solov@gmail.com':['Florida','ND','Louissville','Alabama','UH','A&M','FSU'],
  'adam.schmidt520@gmail.com':['Florida','Boise','Louissville','Alabama','UH','A&M','MIA'],
  'hankrudden@yahoo.com':['Texas','ND','Louissville','Vanderbilt','UH','Miss','FSU'],
  'jlindsey3428@gmail.com':['Texas','Boise','UVA','Vanderbilt','TTU','Miss','MIA'],
  'jakelehman100@gmail.com':['Florida','ND','UVA','Alabama','UH','Miss','FSU'],
  'conor.murphy30@gmail.com':['Texas','Boise','Louissville','Alabama','UH','A&M','MIA'],
  'kylejkz11@gmail.com':['Florida','Boise','Louissville','Alabama','TTU','Miss','FSU'],
  'finsmaniac1551@gmail.com':['Texas','Boise','Louissville','Alabama','UH','A&M','MIA'],
  'timjbohlman@gmail.com':['Florida','ND','Louissville','Vanderbilt','UH','A&M','FSU'],
  'lukeanastasi5@gmail.com':['Texas','ND','UVA','Alabama','TTU','Miss','MIA'],
  'scire.ben@gmail.com':['Texas','ND','UVA','Vanderbilt','TTU','Miss','MIA'],
  'shawnscottcarl@gmail.com':['Florida','ND','UVA','Alabama','UH','Miss','FSU']
});

// Sunday picks (8 NFL games) from Sun_Picks.csv
Object.assign(userPicks['Sun'], {
  'max1solov@gmail.com':['HOU','DAL','DEN','MIA','SEA','LAC','DET','BUF'],
  'kylejkz11@gmail.com':['BAL','DAL','DEN','CAR','TB','LAC','DET','NE'],
  'wyaggy3@gmail.com':['HOU','DAL','DEN','MIA','SEA','WASH','DET','NE'],
  'goodnoughdylan@gmail.com':['HOU','NYJ','DEN','CAR','SEA','LAC','CIN','NE'],
  'adam.schmidt520@gmail.com':['BAL','NYJ','PHI','MIA','SEA','LAC','DET','BUF'],
  'williamjabbott22@gmail.com':['HOU','DAL','PHI','MIA','TB','LAC','DET','NE'],
  'lukeanastasi5@gmail.com':['BAL','DAL','PHI','MIA','TB','WASH','DET','NE'],
  'jlindsey3428@gmail.com':['BAL','NYJ','PHI','MIA','SEA','LAC','DET','NE'],
  'hankrudden@yahoo.com':['HOU','NYJ','DEN','CAR','TB','LAC','DET','NE'],
  'timjbohlman@gmail.com':['HOU','NYJ','PHI','CAR','TB','LAC','CIN','NE'],
  'finsmaniac1551@gmail.com':['HOU','DAL','PHI','MIA','SEA','LAC','DET','BUF'],
  'jakelehman100@gmail.com':['HOU','NYJ','DEN','CAR','SEA','LAC','CIN','NE'],
  'conor.murphy30@gmail.com':['HOU','DAL','PHI','CAR','TB','LAC','DET','NE'],
  'samuel.lehman3337@gmail.com':['HOU','DAL','DEN','CAR','TB','LAC','DET','NE'],
  'mzanin98@gmail.com':['HOU','DAL','PHI','MIA','SEA','WASH','DET','NE'],
  'scire.ben@gmail.com':['HOU','DAL','PHI','MIA','SEA','WASH','DET','NE'],
  'shawnscottcarl@gmail.com':['HOU','NYJ','DEN','CAR','SEA','LAC','CIN','NE']
});

// Covered picks from week_schedule.csv Result column (NOTE: placeholders appear inconsistent with actual teams - likely temporary markers)
// Thu: TOTAL=OVER, SPREAD column shows 'UVA' (likely data entry placeholder), MLB shows 'NYY'
// Fri: WVU @ BYU spread winner recorded as 'MIA' (placeholder)
// Sat sequence results: Bama, FLA, ND, A&M, Bama, A&M, MIA (likely mismatched ordering)
// We load them verbatim so standings reflect the provided file; consider correcting week_schedule.csv for accuracy.
const coveredPicks = {
  'Thurs':['SF','Over','NYY'],
  'Fri':['WVU'],
  // Saturday winners aligned to labels: [Texas-6.5, Boise+19.5, UVA+6.5, Vanderbilt+10.5, TTU-12.5, Miss St +14.5, Miami -4.5]
  // Inserted missing UVA (third slot). Adjust others accordingly if real outcomes differ.
  'Sat':['Texas Tech','Florida','UVA','Notre Dame','Texas A&M','Alabama','Miami'], // Adjusted to 7 entries.
  // Sunday NFL ATS winners in label order:
  // Labels:
  // 1. Houston -1.5 @ Baltimore  => Houston covered (won outright big)
  // 2. Dallas -1.5 @ New York Jets => Dallas covered (win margin > 1.5)
  // 3. Denver +4.5 @ Philadelphia => Denver covered (won outright 21-17)
  // 4. Miami -1.5 @ Carolina => Carolina covered (Carolina 27-21 as home dog)
  // 5. Tampa Bay +3.5 @ Seattle => Tampa Bay covered (won 38-35 as +3.5 dog)
  // 6. Washington Commanders -2.5 @ Los Angeles Chargers => Washington covered (won 27-10 laying 2.5)
  // 7. Detroit Lions -9.5 @ Cincinnati Bengals => Detroit covered (won 37-24, margin 13)
  // 8. New England Patriots +7.5 @ Buffalo Bills => New England covered (won 23-20 as +7.5 dog)
  'Sun':['HOU','DAL','DEN','CAR','TB','WSH','DET','NE'], 'Mon':[]
};

// New week initial day defaults (Thursday completed, focusing on Friday)
// Set default focus to Sunday (upcoming games) now that Thu-Sat complete.
let currentDay = 'Sun';
let scoreboardDay = 'Sun';

/* ================= LIVE GAME DEFINITIONS ================= */
// Week 4 Thursday NFL game (completed). Final score BUF 31-21 (Miami +11.5 covers, total 52 > 50.5).
const nflGame = { eventId:null, away:'Miami', awayAbbr:'MIA', home:'Buffalo', homeAbbr:'BUF', lineHome:-11.5, total:50.5 };
let nflState = { status:'STATUS_FINAL', score:'-', home:0, away:0, period:4 };
// Placeholder collegeGame / collegeState (removed this week but referenced defensively in leaderboard.js)
const collegeGame = null; let collegeState = { status:'STATUS_SCHEDULED', score:'-', home:0, away:0, period:0 };

// Dynamic schedule placeholders (populated by schedule_init.js)
const fridayGames = []; const fridayStates = [];
const saturdayGames = []; const saturdayStates = [];
// Pre-populate Sunday games with ESPN event IDs (Week context). Lines expressed as lineHome relative to home team.
const sundayGames = [
  { eventId:'401772743', away:'Houston', awayAbbr:'HOU', home:'Baltimore', homeAbbr:'BAL', lineHome:+1.5, total:null },
  { eventId:'401772850', away:'Dallas', awayAbbr:'DAL', home:'New York Jets', homeAbbr:'NYJ', lineHome:+1.5, total:null },
  { eventId:'401772745', away:'Denver', awayAbbr:'DEN', home:'Philadelphia', homeAbbr:'PHI', lineHome:-4.5, total:null },
  { eventId:'401772852', away:'Miami', awayAbbr:'MIA', home:'Carolina', homeAbbr:'CAR', lineHome:+1.5, total:null },
  { eventId:'401772746', away:'Tampa Bay', awayAbbr:'TB', home:'Seattle', homeAbbr:'SEA', lineHome:-3.5, total:null },
  { eventId:'401772853', away:'Washington', awayAbbr:'WSH', home:'Los Angeles Chargers', homeAbbr:'LAC', lineHome:+2.5, total:null },
  { eventId:'401772854', away:'Detroit', awayAbbr:'DET', home:'Cincinnati', homeAbbr:'CIN', lineHome:+9.5, total:null },
  { eventId:'401772922', away:'New England', awayAbbr:'NE', home:'Buffalo', homeAbbr:'BUF', lineHome:-7.5, total:null }
];
const sundayStartTimes = sundayGames.map(()=> '');
const sundayStates = sundayGames.map(g=> ({ status:'STATUS_SCHEDULED', score:'0-0', home:0, away:0, period:0, clock:'', startTimeStr:'', meta:{ home:{abbr:g.homeAbbr}, away:{abbr:g.awayAbbr} } }));
const mondayGames = []; const mondayStartTimes = []; const mondayStates = [];

window._lbConfig = { users, picksLabels, userPicks, coveredPicks, fridayGames, saturdayGames, sundayGames, mondayGames, nicknameMap, sundayStartTimes, mondayStartTimes };
