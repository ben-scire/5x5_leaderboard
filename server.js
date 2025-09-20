// Simple Express server to store Sunday picks centrally.
// Run: npm install && node server.js
// Environment variables:
//   PORT (default 3000)
//   ADMIN_TOKEN (set something secret for admin retrieval)
// Data persisted in ./data/sundayPicks.json

const fs = require('fs');
const path = require('path');
const express = require('express');
const cors = require('cors');
const crypto = require('crypto');
const app = express();
app.use(express.json());
app.use(cors());

// Serve static files (leaderboard.html etc.) from project root
app.use(express.static(__dirname));

const DATA_DIR = path.join(__dirname, 'data');
const DATA_FILE = path.join(DATA_DIR, 'sundayPicks.json');
const PASS_FILE = path.join(DATA_DIR, 'passphrases.json');
const SNAP_DIR = path.join(DATA_DIR, 'snapshots');
const MONDAY_FILE = path.join(DATA_DIR, 'mondayPicks.json');
if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR);
if (!fs.existsSync(DATA_FILE)) fs.writeFileSync(DATA_FILE, JSON.stringify({}), 'utf8');
if (!fs.existsSync(PASS_FILE)) fs.writeFileSync(PASS_FILE, JSON.stringify({}), 'utf8');
if (!fs.existsSync(SNAP_DIR)) fs.mkdirSync(SNAP_DIR);
if (!fs.existsSync(MONDAY_FILE)) fs.writeFileSync(MONDAY_FILE, JSON.stringify({}), 'utf8');

function readPicks(){
  try { return JSON.parse(fs.readFileSync(DATA_FILE,'utf8')); } catch(e){ return {}; }
}
function writePicks(obj){ fs.writeFileSync(DATA_FILE, JSON.stringify(obj, null, 2),'utf8'); }
function readMonday(){ try { return JSON.parse(fs.readFileSync(MONDAY_FILE,'utf8')); } catch(e){ return {}; } }
function writeMonday(obj){ fs.writeFileSync(MONDAY_FILE, JSON.stringify(obj, null, 2),'utf8'); }
function snapshotPicks(allPicks, changedUser){
  try {
    const ts = new Date().toISOString().replace(/[:.]/g,'-');
    const userSlug = (changedUser||'all').replace(/[^a-zA-Z0-9]+/g,'_');
    const snapPath = path.join(SNAP_DIR, `${ts}_${userSlug}.json`);
    fs.writeFileSync(snapPath, JSON.stringify({ ts: Date.now(), changedUser, picks: allPicks }, null, 2), 'utf8');
  } catch(e){ /* silent */ }
}

function readPasses(){
  try { return JSON.parse(fs.readFileSync(PASS_FILE,'utf8')); } catch(e){ return {}; }
}
function writePasses(obj){ fs.writeFileSync(PASS_FILE, JSON.stringify(obj, null, 2), 'utf8'); }
function hashPass(p){ return crypto.createHash('sha256').update(p).digest('hex'); }

// Users list (emails) used to seed default passphrases lazily. Keep in sync with frontend user list.
const KNOWN_USERS = [
  'samuel.lehman3337@gmail.com',
  'kylejkz11@gmail.com',
  'lukeanastasi5@gmail.com',
  'goodnoughdylan@gmail.com',
  'williamjabbott22@gmail.com',
  'adam.schmidt520@gmail.com',
  'hankrudden@yahoo.com',
  'shawnscottcarl@gmail.com',
  'max1solov@gmail.com',
  'timjbohlman@gmail.com',
  'jakelehman100@gmail.com',
  'finsmaniac1551@gmail.com',
  'scire.ben@gmail.com'
];

function ensureDefaultPass(email){
  const passes = readPasses();
  if (!passes[email]) { passes[email] = hashPass(email); writePasses(passes); }
}

app.get('/health', (req,res)=>res.json({ ok:true }));

// Auth login: verify passphrase (plain text) against stored hash (default hash(email) if missing)
app.post('/auth/login', (req,res)=>{
  const { userEmail, pass } = req.body || {};
  if (!userEmail || !pass) return res.status(400).json({ error:'Missing credentials' });
  if (!KNOWN_USERS.includes(userEmail)) return res.status(404).json({ error:'User not found' });
  ensureDefaultPass(userEmail);
  const passes = readPasses();
  const ok = passes[userEmail] === hashPass(pass);
  if (!ok) return res.status(401).json({ error:'Invalid passphrase' });
  res.json({ ok:true });
});

// Change passphrase: requires oldPass validation
app.post('/passphrases/change', (req,res)=>{
  const { userEmail, oldPass, newPass } = req.body || {};
  if (!userEmail || !oldPass || !newPass) return res.status(400).json({ error:'Missing fields' });
  if (newPass.length < 4) return res.status(400).json({ error:'New pass too short' });
  if (!KNOWN_USERS.includes(userEmail)) return res.status(404).json({ error:'User not found' });
  ensureDefaultPass(userEmail);
  const passes = readPasses();
  if (passes[userEmail] !== hashPass(oldPass)) return res.status(401).json({ error:'Old pass incorrect' });
  passes[userEmail] = hashPass(newPass);
  writePasses(passes);
  res.json({ changed:true });
});

// Submit or update picks
app.post('/picks/sunday', (req,res)=>{
  const { userEmail, picks } = req.body || {};
  if (!userEmail || !Array.isArray(picks) || picks.length !== 9) {
    return res.status(400).json({ error:'Invalid payload' });
  }
  const all = readPicks();
  all[userEmail] = { picks, ts: Date.now() };
  writePicks(all);
  snapshotPicks(all, userEmail);
  res.json({ saved:true });
});

// Admin fetch all
app.get('/picks/sunday', (req,res)=>{
  const token = req.headers['x-admin-token'] || req.query.adminToken;
  if (!token || token !== process.env.ADMIN_TOKEN) {
    return res.status(401).json({ error:'Unauthorized' });
  }
  res.json(readPicks());
});

// Public status (no picks revealed) for submission count
app.get('/picks/sunday/status', (req,res)=>{
  const all = readPicks();
  res.json({ submitted: Object.keys(all) });
});

// Public full picks (locked phase) - no auth required
// Returns same structure as admin endpoint: { email: { picks: [...], ts: number } }
app.get('/picks/sunday/public', (req,res)=>{
  res.json(readPicks());
});

// ==== MONDAY (MNF) PICKS STORAGE ====
// We'll mirror Sunday approach but with 4 picks per user and separate file.
// Endpoints to add:
//   POST /picks/monday  { userEmail, picks[4] }
//   GET  /picks/monday/status -> { submitted:[emails] }
//   GET  /picks/monday/public -> { email: { picks, ts } }
//   (Optional) admin full not strictly needed distinct from public.
// Implementation inserted below.
app.post('/picks/monday', (req,res)=>{
  const { userEmail, picks, pass } = req.body || {};
  if (!userEmail || !Array.isArray(picks) || picks.length !== 4) {
    return res.status(400).json({ error:'Invalid payload' });
  }
  if (!KNOWN_USERS.includes(userEmail)) return res.status(404).json({ error:'User not found' });
  ensureDefaultPass(userEmail);
  const passes = readPasses();
  if (passes[userEmail] !== hashPass(pass||'')) return res.status(401).json({ error:'Auth failed' });
  const all = readMonday();
  all[userEmail] = { picks, ts: Date.now() };
  writeMonday(all);
  res.json({ saved:true });
});

app.get('/picks/monday/status', (req,res)=>{
  const all = readMonday();
  res.json({ submitted:Object.keys(all) });
});

// Public Monday picks: only expose Ben's picks (scire.ben@gmail.com) for transparency while hiding others.
app.get('/picks/monday/public', (req,res)=>{
  const all = readMonday();
  const filtered = {};
  const benKey = 'scire.ben@gmail.com';
  if(all[benKey]) filtered[benKey] = all[benKey];
  res.json(filtered);
});

// Authenticated fetch for a single user's Monday picks (after login)
app.post('/picks/monday/user', (req,res)=>{
  const { userEmail, pass } = req.body || {};
  if(!userEmail || !pass) return res.status(400).json({ error:'Missing credentials' });
  if (!KNOWN_USERS.includes(userEmail)) return res.status(404).json({ error:'User not found' });
  ensureDefaultPass(userEmail);
  const passes = readPasses();
  if (passes[userEmail] !== hashPass(pass)) return res.status(401).json({ error:'Auth failed' });
  const all = readMonday();
  res.json(all[userEmail] || null);
});

// Port hardcoded to 8000 (remove env usage for simplicity)
const port = 8000;
app.listen(port, ()=> console.log('Sunday picks server listening on port', port));
