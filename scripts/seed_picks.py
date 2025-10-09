"""Seed unified picks.json with blank entries for a given day.

Usage (from repo root):
  python scripts/seed_picks.py            # seeds Thursday with 3 blank picks per ALL_USERS
  python scripts/seed_picks.py --day Fri --slots 5
  python scripts/seed_picks.py --force    # overwrite existing entries for that day

This is helpful to pre-populate the leaderboard with participant emails
before actual picks submissions arrive (so the table is not empty).

Safety: By default, if picks.json already has entries for the target day,
the script aborts unless --force is supplied.
"""
from __future__ import annotations
import json, time, argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
PICKS_FILE = DATA / 'picks.json'
SERVER_FILE = ROOT / 'server.py'

def extract_all_users() -> list[str]:
    # Minimal parse of PHRASE_MAP or ALL_USERS from server.py without importing (avoids side effects)
    text = SERVER_FILE.read_text(encoding='utf-8', errors='ignore')
    # First try to find ALL_USERS = [ ... ] pattern
    import re
    # Fallback: build from PHRASE_MAP keys
    all_users = []
    # Try PHRASE_MAP dict literal
    m = re.search(r'PHRASE_MAP\s*=\s*{([^}]+)}', text, re.MULTILINE | re.DOTALL)
    if m:
        body = m.group(1)
        for em in re.findall(r"'([^']+@[^']+)'", body):
            all_users.append(em.strip())
    # Deduplicate preserving order
    seen = set()
    uniq = []
    for e in all_users:
        if e not in seen:
            seen.add(e); uniq.append(e)
    return uniq

def load_existing():
    if not PICKS_FILE.exists():
        return {}
    try:
        return json.loads(PICKS_FILE.read_text(encoding='utf-8')) or {}
    except Exception:
        return {}

def save(data: dict):
    tmp = PICKS_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2), encoding='utf-8')
    tmp.replace(PICKS_FILE)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--day', default='Thu', help='Canonical day key (Thu/Fri/Sat/Sun/Mon)')
    ap.add_argument('--slots', type=int, default=3, help='Number of pick slots to allocate per user (Thursday=3)')
    ap.add_argument('--force', action='store_true', help='Overwrite existing entries for the day if present')
    args = ap.parse_args()
    day = args.day.strip().title()[:3]
    if day not in ('Thu','Fri','Sat','Sun','Mon'):
        raise SystemExit(f"Unsupported day: {day}")
    slots = max(0, args.slots)
    users = extract_all_users()
    if not users:
        raise SystemExit('Could not extract ANY users from server.py')
    data = load_existing()
    day_map = data.setdefault(day, {})
    if day_map and not args.force:
        raise SystemExit(f"Day '{day}' already has {len(day_map)} entries. Use --force to overwrite.")
    now = int(time.time()*1000)
    new_map = {}
    blank = ['' for _ in range(slots)]
    for em in users:
        new_map[em] = { 'picks': list(blank), 'ts': now }
    data[day] = new_map
    save(data)
    print(f"Seeded {len(users)} users for {day} with {slots} blank pick slots -> {PICKS_FILE}")

if __name__ == '__main__':
    main()
