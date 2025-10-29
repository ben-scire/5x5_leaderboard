# 5x5 Leaderboard Platform

A production-tested web application used to operate a five-day NFL/NCAA pick'em pool. The project combines a Flask backend that manages submissions, locking, and scoring with a lightweight vanilla-JS frontend that renders real-time leaderboards and admin panels. This cleaned public version strips proprietary company integrations while preserving the architecture, data-flow, and tooling that I owned at Icarus Medical.

## High-Level Architecture

```
projects/leaderboard/
├── backend/
│   ├── app.py                # Flask application with REST endpoints and static hosting
│   └── requirements.txt      # Minimal runtime dependencies
├── frontend/
│   ├── public/               # HTML entry points (leaderboard, admin, submissions)
│   └── static/
│       ├── css/              # Shared styling
│       ├── img/              # Branding assets
│       └── js/               # Modularized legacy scripts
├── data/
│   ├── picks/                # Redacted JSON stores used during the 2024 season
│   ├── week_schedule.csv     # Normalized schedule + lock metadata
│   └── recovered/            # Example recovery snapshots + import tooling
├── deploy/                   # Render (PaaS) blueprint for one-click deployment
└── scripts/
    └── legacy/               # Python smoke tests + automation from the live ops run
```

## Backend

* **Framework:** Flask (3.x)
* **Capabilities:**
  * Multi-day submission APIs (Thu–Mon) with per-game locking.
  * Admin overrides, CSV exports, and hydration endpoints used by the live leaderboard.
  * Static hosting for the curated frontend assets in `frontend/`.
* **Configuration:** All persistent data paths are derived from the project root so running locally or deploying to Render requires no path tweaks.
* **Running locally:**
  ```bash
  cd projects/leaderboard
  python -m venv .venv
  source .venv/bin/activate
  pip install -r backend/requirements.txt
  python backend/app.py
  ```
  The server starts on `http://localhost:8000` and serves the public leaderboard at `/`.

## Frontend

* Vanilla JS architecture kept intentionally framework-free for fast cold starts on Render free tier.
* `leaderboard.html` renders the chart-heavy scoreboard driven by `/api/leaderboard`.
* Submission pages (e.g., `/submit_sat.html`) are self-contained experiences that interact with their corresponding API endpoints.
* All CSS/JS is namespaced under `/static/` so the Flask static host can serve assets without extra routing rules.

## Data & Recovery Utilities

* JSON files inside `data/picks/` showcase the storage format for each day. They can be swapped out to simulate new weeks.
* `data/recovered/` illustrates how I kept hot backups while cleaning sensitive user entries.
* The scripted smoke test from production lives at `scripts/legacy/local_smoke_test.py`; it can be adapted to validate API regressions quickly.

## Deployment

The `deploy/render.yaml` file mirrors the Render blueprint that powered the live app. Deploying the sanitized version only requires setting the `PYTHON_VERSION` and `GUNICORN_CMD_ARGS` environment variables documented in that file.

## Next Steps

* Extract the sprawling `app.py` into dedicated blueprints (auth, picks, schedule) — left as future work for the public repo.
* Replace vanilla JS with modern bundles (React/Svelte) once showcasing the legacy UI is no longer necessary for context.

