// Minimal new week config (Thursday-only picks to start), augmented with placeholders
// so existing scripts (which expect all weekday keys) do not throw.
window.LIVE_FETCH_ENABLED = true; // enable live API usage for new week

// Nicknames removed per request; display raw email prefixes / full email.
const nicknameMap = {}; // kept as empty object to avoid errors where referenced

// Labels: New Thursday triple pick (Spread, Total, Prop) + empty arrays for other days to avoid undefined lookups
const picksLabels = {
  'Thu': [ 'NFL: PHI -7.5 @ NYG', 'Total: PHI/NYG O/U 40.5', 'Anytime TD: Dart OR A.J. Brown' ],
  'Fri': [], 'Sat': [], 'Sun': [], 'Mon': []
};

// Users start empty; will be populated on first submission via live APIs (leaderboard_live.js) or manual picks injection.
const users = []; // leaderboard.js will show nothing until at least one pick recorded

// Empty containers – will fill as users submit (server persists in picks.json)
const userPicks = { 'Thu': {}, 'Fri': {}, 'Sat': {}, 'Sun': {}, 'Mon': {} };
// Winners placeholders for each day (avoid undefined access in normalization logic)
const coveredPicks = { 'Thu': [], 'Fri': [], 'Sat': [], 'Sun': [], 'Mon': [] }; // winners TBD

// Focus Thursday initially
let currentDay = 'Thu';
let scoreboardDay = 'Thu';

// Placeholder game arrays (allow existing UI loops to run) – real schedule from /api/schedule later.
const fridayGames = []; const fridayStates = [];
const saturdayGames = []; const saturdayStates = [];
const sundayGames = []; const sundayStartTimes = []; const sundayStates = [];
const mondayGames = []; const mondayStartTimes = []; const mondayStates = [];

window._lbConfig = { users, nicknameMap, picksLabels, userPicks, coveredPicks, fridayGames, saturdayGames, sundayGames, mondayGames, sundayStartTimes, mondayStartTimes };

// Define the Thursday Night NFL game (Eagles @ Giants)
// Spread label shows PHI -7.5 @ NYG, meaning home team (NYG) is +7.5 -> lineHome = +7.5
window.nflGame = {
  eventId: '401772940',
  away: 'Philadelphia Eagles',
  awayAbbr: 'PHI',
  home: 'New York Giants',
  homeAbbr: 'NYG',
  lineHome: 7.5, // Giants are +7.5
  total: 40.5
};

// Initial live state placeholder consumed by leaderboard.js updateNFLGame()
window.nflState = {
  status: 'STATUS_SCHEDULED',
  score: '0-0',
  home: 0,
  away: 0,
  period: 0,
  clock: ''
};
