# Leaderboard & Sunday Picks Backend

This project now serves a live multi-day (Thu–Mon) pick set with per-pick kickoff locking, password accounts (seeded from legacy phrases), and a unified Flask backend. Legacy Sunday phrase endpoints have been removed.

## Components

* `leaderboard.html` + JS/CSS – Frontend UI (chart, scoreboard, picks, Sunday form)
* `server.py` – Flask backend (unlock, submit, admin, status, Monday CSV reader)
* `data/sunday_picks.json` – Persistent JSON storage (auto-created)
* `09_15_Picks.csv` – Authoritative Monday (MNF) picks source (locked)

## Core API (New Auth + Picks)

| Method | Path | Purpose | Auth |
| ------ | ---- | ------- | ---- |
| POST | /api/auth/create | Claim seeded account (first time) or create allowed email | none (email must be whitelisted) |
| POST | /api/auth/login | Login and receive bearer token | email/password |
| GET  | /api/auth/status | Validate existing token (silent reuse) | Bearer token |
| GET  | /api/schedule | Current parsed schedule (definitions) | public |
| GET  | /api/schedule/countdowns | Per-pick ms until lock (0 = locked) | public |
| GET  | /api/picks/get?day=Sun | Fetch user picks + lock mask | Bearer token |
| POST | /api/picks/save | Save (only unlocked indices update) | Bearer token |
| GET  | /api/picks/public?day=Sat | Public view (all users & timestamps) | public |
| GET  | /picks/monday/official | Legacy MNF authoritative CSV (still used) | public |
| GET  | /healthz | Service/file status | public |

Removed (Return 410 / not present): /api/unlock, /api/submit, /api/all, /picks/sunday/*, /api/picks/unlock, /api/picks/submit.

Tokens are HMAC signed with SECRET_KEY and valid for 7 days.

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

## Unified Multi-Day Picks

All picks (Thu → Mon) now live in a single JSON file `data/picks.json` keyed by day then email:

```json
{
  "Sat": { "user@example.com": { "picks": ["..."], "ts": 1695080000000 } },
  "Sun": { ... }
}
```

Each day array length equals the number of pick definitions parsed from the schedule CSV. Editing is allowed until each pick's underlying game kickoff time; locking is per index (spread/total tied to the game). Props without a gameIndex remain editable until manually locked (future enhancement).

Front end polls `/api/schedule/countdowns` every 15 seconds; once a pick hits 0 ms it is disabled.

If a user tries to modify a locked slot they receive `409 locked_picks` with indices of disallowed changes.

### Schedule CSV (Row-per-Pick Schema)

File: `data/week_schedule.csv`

Header columns:

```csv
Day,Sport,EventId,Away,AwayAbbr,Home,HomeAbbr,Market,Line,Total,StartTimeET,PropLabel,Date,Result
```

Semantics:
 
* Market: SPREAD | TOTAL | PROP
* Line: Spread number stored as home-team based value (positive means home is favored, negative means home is underdog). Users will submit their side separately when making picks.
* Total: Only for TOTAL rows.
* PropLabel: Text label displayed for PROP rows.
* Date: YYYY-MM-DD used for kickoff parsing -> ISO timestamp (US/Eastern). If all Dates omitted the parser infers sequential dates for Thu–Mon (not recommended for production; supply explicit dates).
* Result: For SPREAD rows put the covering side abbreviation (HOME team abbr or AWAY team abbr). For TOTAL rows put OVER or UNDER (or PUSH). For PROP rows put YES / NO (or leave blank). (Previously HIT/MISS; now replaced by outcome side so user scoring derives from matching their pick to the covering result.)
 

### Updating Results

1. After a game finishes determine: (a) covering side for spread (b) Over/Under for totals (c) YES/NO for prop (or PUSH if applicable).
2. Edit the CSV setting the `Result` column accordingly (e.g. MIA, OVER, PUSH).
3. Commit & push (or POST `/api/schedule/reload`) to refresh cache.
4. Future scoring integration will award a point when a user's stored pick (their chosen side or Over/Under) equals the pick definition's `result` value.

### Live Leaderboard Scoring API

Endpoint: `GET /api/leaderboard`

Response shape:
 
```json
{
  ok: true,
  totalPossible: 25,        // Sum of all pick definitions across Thu-Mon (dynamic)
  entries: [
    { email: "user@example.com", score: 7, answered: 9, totalPossible: 25 },
    ... sorted by highest score desc then fewest answered then email
  ],
  generated: 1737052800000   // server timestamp ms
}
```

Scoring rules:
 
* A pick counts only if schedule `result` for that index is non-empty and not PUSH.
* User pick is normalized (case-insensitive, maps O->OVER, U->UNDER, Y->YES, N->NO).
* Award 1 point when user pick exactly matches the pick's `result`.
* PUSH never awards a point and is skipped (not counted in answered).
* `answered` = number of gradable (non-empty, non-PUSH result) picks where user entered a value (hit or miss). This helps tie-break with identical scores.

Intended frontend usage:
 
* Poll every 30–60s (or via manual refresh) and display each user's `score / totalPossible`.
* Optionally show accuracy = score / answered if you want a secondary metric.

### Adding a New Week

1. Copy previous `week_schedule.csv` → update EventId, teams, spreads, totals, dates.
2. Remove old Results except any already final (e.g., Thursday after it plays).
3. Deploy; users can immediately begin editing future-day picks.

<!-- Trimmed legacy duplicated sections removed to satisfy markdown lint rules -->
<!-- (Removed duplicate H1 to satisfy markdown lint MD025) -->

This project previously included an alternative Node/Express implementation (server.js) which has now been removed. Flask is the only backend.

## Render Deployment (Recommended)

The repository now includes `render.yaml` so you can deploy directly from GitHub:

1. Push this repository to GitHub (ensure `render.yaml` at repo root or service root).
2. In Render dashboard: New + Blueprint, point at repo.
3. Confirm service name and region. A persistent disk (1GB) is provisioned automatically for `/data` (picks JSON).
4. Deploy. Render sets `$PORT`; `gunicorn` binds to it per `startCommand`.
5. Access: `https://<service>.onrender.com/leaderboard.html`.

Environment Variables (optional):

* None required initially. Future: add `ADMIN_EMAILS`, hashed phrase salts, etc.

Persistence:

* `data/` is stored on the attached disk. Re-deploys do not wipe picks.
* If Blueprint import errors on `render.yaml`, ensure the file uses `disk:` (singular) not `disks:` and that you replace `SECRET_KEY` value in the dashboard (the committed value is a placeholder).

## Archival Policy

Legacy raw form exports, historical JSON pick snapshots, and previous-week data are moved under `archive/` to keep the active service surface minimal:

Structure:

```text
archive/
  legacy_forms/              # Old Google Form CSV dumps (kept for auditing)
  old_weeks_data/            # Previous implementation directory (static reference)
    data/                    # Legacy JSON stores (ignored by git after move)
```

Git Ignore Rules:

* All JSON + snapshot contents under `archive/old_weeks_data/data/` are ignored.
* New ad‑hoc CSV exports at repo root are ignored; move anything you want to preserve into `archive/legacy_forms/`.

Operational Guidance:

* Only `data/week_schedule.csv` plus unified picks JSON (runtime) drive the current week.
* Remove or archive any stray `*_picks.json` files that are not part of the unified system.
* When starting a new season, compress older archived weeks if size becomes material.

Health Check:

* Render pings `/healthz` to verify instance health.

Scaling:

* Starter plan single instance is sufficient (very low CPU). Cron tasks not required.

## Next Steps Ideas

* Live auto-grading using Result column
* Rate limiting & brute-force protection
* Admin endpoint to list all picks for a day
* Logout token revocation list (in-memory or short TTL)
* Schedule validation script (lint spreads, totals, duplicate eventIds)

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


### Current Backend Choice

Node artifacts removed. Flask (`server.py`) is the single source of truth.

