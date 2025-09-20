// Configuration & static data extracted from leaderboard.html
// Exposes globals for simplicity (no module system). Later we can namespace if desired.

/* ================= USERS & PICKS DATA ================= */
// Added 'sun' field for upcoming Sunday scoreboard integration
// Week 4 expanded roster (17 users) – previous week scores reset to 0
const users = [
  { username:'samuel.lehman3337@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'kylejkz11@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'lukeanastasi5@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'goodnoughdylan@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'williamjabbott22@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'adam.schmidt520@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'hankrudden@yahoo.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'shawnscottcarl@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'max1solov@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'timjbohlman@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'jakelehman100@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'finsmaniac1551@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'scire.ben@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'mzanin98@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'jlindsey3428@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'tomlinson6267@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 },
  { username:'conor.murphy30@gmail.com', thurs:0, fri:0, sat:0, sun:0, mon:0 }
];

// Updated nicknames per user request
const nicknameMap = {
  'samuel.lehman3337@gmail.com':'Sam',
  'kylejkz11@gmail.com':'Kyle',
  'lukeanastasi5@gmail.com':'Luke',
  'goodnoughdylan@gmail.com':'Dylan',
  'williamjabbott22@gmail.com':'Abbo',
  'adam.schmidt520@gmail.com':'Schmidt',
  'hankrudden@yahoo.com':'Hank',
  'shawnscottcarl@gmail.com':'Shawn',
  'max1solov@gmail.com':'Solov',
  'timjbohlman@gmail.com':'Bohlman',
  'jakelehman100@gmail.com':'Jake',
  'finsmaniac1551@gmail.com':'Nick',
  'scire.ben@gmail.com':'Ben',
  'mzanin98@gmail.com':'matteo',    // was Zan
  'jlindsey3428@gmail.com':'jlinds', // was JL
  'tomlinson6267@gmail.com':'jay',   // was Tom
  'conor.murphy30@gmail.com':'murph' // was Conor
};

// Base labels: Thursday and Friday locked historical; all other days filled dynamically from schedule_init.js
const picksLabels = {
  'Thurs':[ 'MIA +11.5 @ BUF', 'O/U 50.5 (MIA/BUF)', 'TD Prop (Yes/No)' ],
  'Fri':[ 'Tulsa +11.5 @ Oklahoma State', 'Iowa -2.5 @ Rutgers' ],
  'Sat':[], 'Sun':[], 'Mon':[]
};

// New week: userPicks with static locked Thursday picks embedded.
// Thursday columns order: [Spread Pick, Total Pick, TD Prop]
const userPicks = { 'Thurs': {}, 'Fri': {}, 'Sat': {}, 'Sun': {}, 'Mon': {} };

// Week 4 Thursday static picks (FINAL & LOCKED) — replace values here only if rebuilding historical data.
Object.assign(userPicks['Thurs'], {
  // Week 4 Thursday ACTUAL submissions from 09_18_Picks.csv (LOCKED)
  'samuel.lehman3337@gmail.com':['MIA','Over','Yes'],
  'mzanin98@gmail.com':['BUF','Under','Yes'],
  'scire.ben@gmail.com':['MIA','Under','No'],
  'shawnscottcarl@gmail.com':['BUF','Under','Yes'],
  'max1solov@gmail.com':['BUF','Under','No'],
  'jlindsey3428@gmail.com':['MIA','Over','No'],
  'timjbohlman@gmail.com':['MIA','Under','Yes'],
  'kylejkz11@gmail.com':['BUF','Under','No'],
  'conor.murphy30@gmail.com':['BUF','Over','Yes'],
  'tomlinson6267@gmail.com':['BUF','Over','Yes'],
  'goodnoughdylan@gmail.com':['BUF','Under','Yes'],
  'finsmaniac1551@gmail.com':['MIA','Over','Yes'],
  'adam.schmidt520@gmail.com':['MIA','Over','Yes'],
  'williamjabbott22@gmail.com':['BUF','Under','No'],
  'jakelehman100@gmail.com':['MIA','Under','No'],
  'hankrudden@yahoo.com':['BUF','Under','Yes'],
  'lukeanastasi5@gmail.com':['MIA','Over','Yes']
});

// Week 4 Friday static picks (FINAL & LOCKED) — from 09_19_Picks.csv
Object.assign(userPicks['Fri'], {
  'adam.schmidt520@gmail.com':['Tulsa','Rutgers'],
  'jlindsey3428@gmail.com':['Tulsa','Rutgers'],
  'tomlinson6267@gmail.com':['Oklahoma State','Rutgers'],
  'timjbohlman@gmail.com':['Tulsa','Iowa'],
  'samuel.lehman3337@gmail.com':['Tulsa','Iowa'],
  'max1solov@gmail.com':['Tulsa','Iowa'],
  'williamjabbott22@gmail.com':['Oklahoma State','Iowa'],
  'mzanin98@gmail.com':['Oklahoma State','Iowa'],
  'kylejkz11@gmail.com':['Tulsa','Iowa'],
  'hankrudden@yahoo.com':['Tulsa','Iowa'],
  'jakelehman100@gmail.com':['Oklahoma State','Rutgers'],
  'shawnscottcarl@gmail.com':['Oklahoma State','Iowa'],
  'goodnoughdylan@gmail.com':['Oklahoma State','Iowa'],
  'finsmaniac1551@gmail.com':['Tulsa','Iowa'],
  'scire.ben@gmail.com':['Oklahoma State','Iowa'],
  'lukeanastasi5@gmail.com':['Tulsa','Iowa'],
  'conor.murphy30@gmail.com':['Tulsa','Iowa']
});

// Friday & later picks now provided at runtime via unified picks endpoints; no static seed.

// Seed Thursday and Friday winners (final): Thursday - MIA covered, game went Over 50.5, TD Prop hit (Yes); Friday - Tulsa and Iowa won
const coveredPicks = { 
  'Thurs':['MIA','Over','Yes'], 
  'Fri': ['Tulsa','Iowa'], 
  'Sat': [], 'Sun': [], 'Mon': [] 
};

// New week initial day defaults (Thursday completed, focusing on Friday)
let currentDay = 'Fri';
let scoreboardDay = 'Fri'; // scoreboard shows upcoming Friday slate initially

/* ================= LIVE GAME DEFINITIONS ================= */
// Week 4 Thursday NFL game (completed). Final score BUF 31-21 (Miami +11.5 covers, total 52 > 50.5).
const nflGame = { eventId:null, away:'Miami', awayAbbr:'MIA', home:'Buffalo', homeAbbr:'BUF', lineHome:-11.5, total:50.5 };
let nflState = { status:'STATUS_FINAL', score:'-', home:0, away:0, period:4 };
// Placeholder collegeGame / collegeState (removed this week but referenced defensively in leaderboard.js)
const collegeGame = null; let collegeState = { status:'STATUS_SCHEDULED', score:'-', home:0, away:0, period:0 };

// Dynamic schedule placeholders (populated by schedule_init.js)
const fridayGames = []; const fridayStates = [];
const saturdayGames = []; const saturdayStates = [];
const sundayGames = []; const sundayStartTimes = []; const sundayStates = [];
const mondayGames = []; const mondayStartTimes = []; const mondayStates = [];

window._lbConfig = { users, picksLabels, userPicks, coveredPicks, fridayGames, saturdayGames, sundayGames, mondayGames, nicknameMap, sundayStartTimes, mondayStartTimes };
