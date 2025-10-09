// Minimal new week config (Thursday-only picks to start).
// We purposely strip prior week static data; dynamic data now comes from unified picks API.
// If a value is missing client code will fallback gracefully.
window.LIVE_FETCH_ENABLED = true;

// Nicknames (retain for display)
const nicknameMap = {
  'adam.schmidt520@gmail.com':'Schmidt','conor.murphy30@gmail.com':'Murph','finsmaniac1551@gmail.com':'Nick','goodnoughdylan@gmail.com':'Dylan','hankrudden@yahoo.com':'Hank','jakelehman100@gmail.com':'Jake','jlindsey3428@gmail.com':'JLinds','kylejkz11@gmail.com':'Kyle','lukeanastasi5@gmail.com':'Luke','max1solov@gmail.com':'Solov','mzanin98@gmail.com':'Matteo','samuel.lehman3337@gmail.com':'Sam','scire.ben@gmail.com':'Ben','shawnscottcarl@gmail.com':'Shawn','timjbohlman@gmail.com':'Bohlman','williamjabbott22@gmail.com':'Abbo','wyaggy3@gmail.com':'Wyatt'
};

// Labels: New Thursday triple pick (Spread, Total, Prop)
const picksLabels = { 'Thurs': [ 'NFL: PHI -7.5 @ NYG', 'Total: PHI/NYG O/U 40.5', 'Anytime TD: Dart OR A.J. Brown' ] };

// Empty containers – will fill as users submit (server persists in picks.json)
const userPicks = { 'Thurs': {} };
const coveredPicks = { 'Thurs': [] }; // winners TBD

// Focus Thursday initially
let currentDay = 'Thurs';
let scoreboardDay = 'Thurs';

// Placeholder game arrays (allow existing UI loops to run) – real schedule from /api/schedule later.
const fridayGames = []; const fridayStates = [];
const saturdayGames = []; const saturdayStates = [];
const sundayGames = []; const sundayStartTimes = []; const sundayStates = [];
const mondayGames = []; const mondayStartTimes = []; const mondayStates = [];

window._lbConfig = { nicknameMap, picksLabels, userPicks, coveredPicks, fridayGames, saturdayGames, sundayGames, mondayGames, sundayStartTimes, mondayStartTimes };
