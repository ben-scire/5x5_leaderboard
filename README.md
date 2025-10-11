# Leaderboard & Picks Platform (Week System)

This project serves a live leaderboard plus multi-day pick submission (Thu–Mon) via a Flask backend.

Update (Friday complete): Friday submission page has been retired (games locked/final). Only Saturday submission link remains active on the homepage.

## Components

* `leaderboard.html` + JS/CSS – Frontend UI (chart, scoreboard, picks, Sunday form)
* `server.py` – Flask backend (unlock, submit, admin, status, Monday CSV reader)
* `data/sunday_picks.json` – Persistent JSON storage (auto-created)
* `09_15_Picks.csv` – Authoritative Monday (MNF) picks source (locked)

## Current Core API (Token Auth)
 
Token / Account (all JSON):

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | /api/auth/create | Claim (or create) account: email + password (3+ chars). If email was auto-seeded you overwrite its seeded password once. |
| POST | /api/auth/login | Login and receive bearer token |
| GET  | /api/auth/status | Validate token & return email/admin status |

Schedule & Picks:
| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | /api/schedule | Structured schedule (games + pick definitions) |
| GET | /api/schedule/countdowns | Per-pick ms until lock (0 if locked) |
| GET | /api/picks/get?day=Day | Get your picks + lock matrix for that day (Bearer) |
| POST | /api/picks/save | Save/overwrite unlocked picks (Bearer) |
| GET | /api/picks/public?day=Day | Public submissions (legacy format) |

Legacy phrase endpoints now return HTTP 410 (Gone): `/api/picks/unlock`, `/api/picks/submit`.

| Method | Path | Purpose | Auth |
| ------ | ---- | ------- | ---- |
| GET | /api/status | Submission count | None |
| POST | /api/unlock | Validate phrase & fetch existing picks | email + phrase |
| POST | /api/submit | One-time submission (must be 9 picks) | email + phrase |
| POST | /api/all | Admin full list | admin email + phrase |
| GET  | /picks/monday/official | Locked MNF picks (from CSV) | None |

Deprecated / Locked:
| POST | /picks/monday | (returns 403 locked) | N/A |
| POST | /picks/monday/all | (returns 410 gone) | N/A |

All requests/response bodies are JSON. Phrases compared case-insensitively.

## Run (Windows PowerShell)

```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
pip install -r requirements.txt
python server.py
```


Server binds `0.0.0.0:8000`. Share: `http://YOUR_PUBLIC_IP:8000/leaderboard.html`.

## Data Backup

Copy the JSON periodically:
## Deployment (Render)

1. Push repo to GitHub. Ensure current week files are committed: `data/week_schedule.csv`, `leaderboard.html`, `leaderboard.js`, `schedule_init.js`, `server.py`.
2. Create a Render Web Service.
  * Root Directory: `5x5_leaderboard` (if repository root contains other folders)
  * Runtime: Python
  * Build Command: `pip install -r requirements.txt`
  * Start Command: `gunicorn -w 2 -b 0.0.0.0:$PORT server:app`
3. Persistent Disk:
  * Mount Path: `/opt/render/project/src/data`
  * Size: 1 GB (stores picks, users, schedule snapshot)
4. Environment Variables:
  * `SECRET_KEY` = long random hex (keeps tokens valid across deploys)
5. Health Check Path: `/healthz`
6. After deploy visit `/leaderboard.html` and `/picks.html`.
7. Weekly schedule update: replace `data/week_schedule.csv`, then either redeploy or POST `/api/schedule/reload` with admin email + phrase.

Admin Schedule Reload example (PowerShell):

```powershell
Invoke-RestMethod -Uri https://YOUR_SERVICE.onrender.com/api/schedule/reload -Method POST -Body (@{ email='scire.ben@gmail.com'; phrase='admin' } | ConvertTo-Json) -ContentType 'application/json'
```

If Monday only has (PROP, SPREAD, TOTAL) the UI adapts automatically.


```powershell
copy data\sunday_picks.json backups\sunday_picks_$(Get-Date -Format yyyy-MM-dd_HH-mm-ss).json
```


## Resetting A User (Manual)

Remove that user's object from `data/sunday_picks.json` (while server stopped). Restart server; user can resubmit.

## Security Notes

Plain HTTP + plaintext phrases. Do NOT reuse real passwords. For better security place behind HTTPS (Caddy, Nginx, Cloudflare Tunnel) and optionally hash phrases server-side.

## Future Ideas

* Hash (SHA256) phrases before storing/comparing
* CSV export route
* Rate limiting per IP
* WebSocket or SSE push for live count
* Admin revoke / reset route

## Admin

Unlock as Ben (`admin` phrase) to view full submissions table. Table refreshes each unlock; you can also refresh page.

Enjoy.

## Monday (MNF) Locked Picks

Monday night picks are no longer submitted via the web form. They are sourced exclusively from the CSV file (`09_15_Picks.csv`) checked into the repository and read by the backend endpoint `/picks/monday/official`.

Rules:

* First occurrence of an email in the CSV wins (duplicates ignored).
* Missing cells become `NA`.
* Known email typo auto-corrected (`hankruddenn@` -> `hankrudden@`).
* If Nick (`finsmaniac1551@gmail.com`) is absent, he is injected with all `NA` picks so the UI stays stable.

To update Monday picks for a new week, replace the CSV file (or add a new dated CSV and update the path constant in `server.py`) before the site loads. No runtime edits are accepted.

Endpoints responding with archive / deprecated status ensure past submission UIs cannot alter data. The frontend script `monday_submit.js` has been replaced with a static notice.

## Account & Auth Model

1. On startup, every email in the roster is auto-seeded into `users.json` with a hashed version of its legacy phrase (flag `seeded: true`).
2. A user visits the site, enters the same email under "Create Account" and chooses a new password (≥3 chars). If it was seeded, the backend overwrites the seeded hash and stamps `claimed`.
3. User receives a bearer token (HMAC signed with `SECRET_KEY`) valid for 7 days. Token is stored in `localStorage` and reused on refresh via `/api/auth/status`.
4. Picks are editable per day until kickoff (derived from `Date` + `StartTimeET` in `week_schedule.csv`). Each pick line tied to a game locks individually; props without a start remain open (can refine later).

Environment variable strongly recommended:

```
SECRET_KEY=<long random string>
```

Without it, an ephemeral secret is generated (tokens invalidate after restart).

## Countdown / Locking

Frontend polls `/api/schedule/countdowns` every 15s. Each pick row shows a mm:ss countdown until lock, then disables input and marks Locked.

## Deprecation Notes

Old phrase-based submission endpoints are deprecated (410). Monday CSV logic remains for historical locked display, but all new weekly pick flows use token auth.

## Minimal User Onboarding Text (Share with Players)

1. Go to site URL.
2. Click Create Account; enter the same email you used previously; choose a new password (≥3 characters).
3. Select a day, fill picks; click Save.
4. You can edit any unlocked pick up to kickoff (watch the countdown). After it locks, that slot is frozen.
5. Your session persists for a week; logout if using a shared computer.

## Admin Tips

* To force re-seed a user, delete their entry in `data/users.json` and restart — they can recreate.
* To adjust kickoff lock, edit `week_schedule.csv` (Date + StartTimeET), then POST `/api/schedule/reload` (admin phrase still required) or redeploy.
* Back up `data/picks.json` regularly.


Sunday picks still use JSON submission with phrase auth. Monday logic is isolated so you can iterate Sunday independently.

<!-- Trimmed legacy duplicated sections removed to satisfy markdown lint rules -->
<!-- (Removed duplicate H1 to satisfy markdown lint MD025) -->

This project now supports centralized Sunday pick submission using a small Node/Express server.

## Local Development

1. Install dependencies:

```powershell
npm init -y
npm install express
```


1. Set an admin token (PowerShell example):

```powershell
$env:ADMIN_TOKEN = "change_me_secret"
```

1. Start the server:

```powershell
node server.js
```

1. Open `leaderboard.html` in a browser. Update client JS to post Sunday picks to your server URL (see below adjustments you can integrate).

## API

POST /picks/sunday


```json
{
  "userEmail": "scire.ben@gmail.com",
  "picks": ["LV","MIA","PIT","SF","DET","HOU","BAL"]
}
```
Returns `{ saved: true }` on success.


GET /picks/sunday (Admin only)
Headers: `x-admin-token: <ADMIN_TOKEN>` OR query `?adminToken=...`
Returns JSON object mapping userEmail to `{ picks, ts }`.

## Persistence

Data stored in `data/sundayPicks.json`.

## Deployment Options

Any service that can run Node (Railway, Render, Fly.io) works. Set `ADMIN_TOKEN` as a secret on the platform.

If you were previously sharing the page via:

```powershell
python -m http.server 8000
```

You can instead run the Node server (which also serves the static HTML) and get centralized pick storage:

```powershell
$env:ADMIN_TOKEN="change_me_secret"
node server.js
```

Then access: `http://YOUR_IP:8000/leaderboard.html`

## Client Integration (Manual Step)

Inside `leaderboard.html`, replace local-only saving for Sunday picks with a `fetch` call:

```javascript
fetch('https://YOUR_SERVER/picks/sunday', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ userEmail: lockedSundayUser, picks })
});
```

And when Ben (admin) logs in, request:

```javascript
fetch('https://YOUR_SERVER/picks/sunday', { headers: { 'x-admin-token': 'YOUR_ADMIN_TOKEN' }})
  .then(r=>r.json())
  .then(data => /* render table */);
```

Do NOT expose the admin token publicly.

## Next Steps Ideas

* Add kickoff auto-lock based on time.
* Add hashing of passphrases instead of plain text client-side.
* Persist Saturday picks similarly if needed.

## Production Deployment (GoDaddy Domain)

You have two backend codepaths: legacy Node (`server.js`) and newer Flask (`server.py`). Pick one for production to keep resource use low.

### Option A: Deploy Flask (recommended for current week logic)

1. Server (VPS) prerequisites: Python 3.11+, `git`, `ufw` firewall allowing 80/443.

1. Clone repo:

```bash
git clone https://YOUR_REPO.git && cd Leaderboard_Site
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

1. Test locally:

```bash
python server.py
# Visit http://SERVER_IP:8000/leaderboard.html
```

1. Create systemd unit `/etc/systemd/system/leaderboard.service`:

```ini
[Unit]
Description=Leaderboard Flask
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/leaderboard
ExecStart=/opt/leaderboard/venv/bin/gunicorn -w 2 -b 127.0.0.1:8100 server:app
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

(Adjust path if different; we run behind Nginx on 8100.)

1. Nginx site `/etc/nginx/sites-available/leaderboard`:

```nginx
server {
  listen 80;
  server_name 5x5coach.com www.5x5coach.com;
  location /static/ { alias /opt/leaderboard/static/; }
  location / {
   proxy_pass http://127.0.0.1:8100/;
   proxy_set_header Host $host;
   proxy_set_header X-Forwarded-For $remote_addr;
  }
}
```

1. Enable & start:

```bash
sudo ln -s /etc/nginx/sites-available/leaderboard /etc/nginx/sites-enabled/
sudo systemctl enable --now leaderboard
sudo nginx -t && sudo systemctl reload nginx
```

1. DNS at GoDaddy: set A record for `@` and `www` to VPS IP.

1. TLS (Certbot):

```bash
sudo snap install --classic certbot
sudo certbot --nginx -d 5x5coach.com -d www.5x5coach.com --redirect
```

### Option B: Deploy Node
Run a systemd service executing: `node server.js` bound to :8000, proxy via Nginx similarly. Replace `proxy_pass` port with 8000.

### Throttled Live Fetching
`leaderboard.js` now fetches ESPN summaries no more than once every 60s (internal guard + interval) to minimize risk of rate limiting.

### Data Persistence
Ensure `/opt/leaderboard/data` owned by service user (e.g., `chown -R leaderboard:leaderboard data`). Consider a cron job backup:
```bash
0 * * * * tar -czf /var/backups/leaderboard-data-$(date +\%Y\%m\%d\%H).tgz -C /opt/leaderboard data
```

### Choosing Back End
If you only need static leaderboard + CSV ingest + minimal auth, prefer Flask for smaller dependency surface (just Flask + gunicorn). Remove unused platform (delete `server.js` or `server.py`) to avoid confusion.

