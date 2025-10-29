# Sports Analytics Portfolio

This repository now serves as a polished portfolio for showcasing end-to-end product work that blends data engineering, web development, and operational tooling for live sports pools. Each project has a self-contained backend, frontend, and data pipeline documentation so reviewers can quickly understand scope and responsibilities.

## Project Index

| Project | Description |
| ------- | ----------- |
| [`projects/leaderboard`](projects/leaderboard/README.md) | Full-stack leaderboard and pick-submission platform used to run a five-day NFL/NCAA pick'em contest. Includes Flask backend, vanilla JS frontend, and data automation scripts. |

Additional case studies will be staged under `projects/` as they are cleaned for public review.

## Local Development

Each project folder contains its own README with setup, architecture notes, and scripts. Typical workflow:

1. Pick a project directory (for example `projects/leaderboard`).
2. Follow the backend setup instructions (usually `python -m venv .venv && pip install -r backend/requirements.txt`).
3. Start the backend server (for example `python -m backend.app`).
4. Open the documented frontend entry point.

Shared resources such as datasets or recovery snapshots live alongside each project under `projects/<name>/data`.

## Tooling Highlights

* **Python / Flask** – rapid API development with structured services and tests.
* **Vanilla JS + Chart.js** – fast-loading dashboards without heavy frameworks.
* **Automated scripts** – data ingest and smoke tests (see `projects/leaderboard/scripts`).
* **Render deployment config** – reproducible cloud deploy setup in `projects/<name>/deploy/`.

## License

This repository is shared for recruiting review. Do not redistribute proprietary data that might be reintroduced in future updates.
