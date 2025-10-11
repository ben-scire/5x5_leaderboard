#!/usr/bin/env python3
"""Recover/aggregate all pick submissions across all days (Thu–Sun) from every on-disk source.

Why: If in-memory state drifted or JSON hot reload missed earlier entries, the CSV logs
(append-only) are the ground-truth history of submissions. For each day we take the LAST
row per email (latest submission) so you can see who actually submitted. This helps
reconcile cases where /status endpoints show someone as missing.

Outputs (default):
- Pretty printed JSON to stdout summarizing per-day latest picks and counts.
Optional flags:
  --out JSON_PATH            Write recovered JSON structure to a file.
  --csv CSV_PATH             Write a wide CSV (day,email,pick1,pick2,...) for all days.
  --include-empty            Include emails with only blanks (otherwise blank-only rows are skipped).

Data precedence per day (later sources overwrite earlier):
  Thursday: data/picks/thursday_picks.json (only authoritative source)
  Friday:   friday_picks_log.csv  -> friday_locked.json (if exists) -> friday_picks.json
  Saturday: saturday_picks_log.csv -> saturday_locked.json (if exists) -> saturday_picks.json
  Sunday:   sunday_picks_log.csv  -> sunday_locked.json (if exists) -> sunday_picks.json

The CSV log is first so that any later lock snapshot or JSON (which might be stale) does NOT erase
newer log entries. Locked snapshot can override if it contains emails absent from the log.

NOTE: This script is read-only (except for optional output files) and safe to run anytime.
"""

from __future__ import annotations
import argparse, csv, json, pathlib, sys
from typing import Dict, List, Tuple

BASE = pathlib.Path('data/picks')

# Label counts (mirrors server expectations). Adjust if schedule changes.
THU_LEN = 3   # spread, total, prop
FRI_LEN = 2
SAT_LEN = 6
SUN_LEN = 8

# File paths
THU_JSON = BASE / 'thursday_picks.json'
FRI_JSON = BASE / 'friday_picks.json'
FRI_LOG  = BASE / 'friday_picks_log.csv'
FRI_LOCK = BASE / 'friday_locked.json'
SAT_JSON = BASE / 'saturday_picks.json'
SAT_LOG  = BASE / 'saturday_picks_log.csv'
SAT_LOCK = BASE / 'saturday_locked.json'
SUN_JSON = BASE / 'sunday_picks.json'
SUN_LOG  = BASE / 'sunday_picks_log.csv'
SUN_LOCK = BASE / 'sunday_locked.json'

DayInfo = Tuple[str, int, pathlib.Path, pathlib.Path, pathlib.Path]

FRI_INFO: DayInfo = ('Fri', FRI_LEN, FRI_JSON, FRI_LOG, FRI_LOCK)
SAT_INFO: DayInfo = ('Sat', SAT_LEN, SAT_JSON, SAT_LOG, SAT_LOCK)
SUN_INFO: DayInfo = ('Sun', SUN_LEN, SUN_JSON, SUN_LOG, SUN_LOCK)


def _safe_load_json(path: pathlib.Path):
    if path.exists():
        try:
            with path.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def _normalize_list(picks, length: int) -> List[str]:
    out: List[str] = []
    if isinstance(picks, list):
        out = [str(p or '').strip().upper() for p in picks[:length]]
    while len(out) < length:
        out.append('')
    return out


def _latest_from_log(log_path: pathlib.Path, length: int) -> Dict[str, List[str]]:
    if not log_path.exists():
        return {}
    latest: Dict[str, List[str]] = {}
    try:
        with log_path.open('r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if not row or len(row) < 2:
                    continue
                # Format: ts_iso,email,pick1,...
                email = row[1].strip().lower()
                picks = [p.strip().upper() for p in row[2:2+length]]
                while len(picks) < length:
                    picks.append('')
                latest[email] = picks
    except Exception:
        pass
    return latest


def _merge(dest: Dict[str, List[str]], src: Dict[str, List[str]]):
    for k, v in src.items():
        dest[k] = v


def recover_day(name: str, length: int, json_file: pathlib.Path, log_file: pathlib.Path, lock_file: pathlib.Path) -> Dict[str, List[str]]:
    recovered: Dict[str, List[str]] = {}
    # 1. CSV log latest (most comprehensive chronological history)
    recovered.update(_latest_from_log(log_file, length))
    # 2. Locked snapshot (if it exists) can add missing emails
    lock_data = _safe_load_json(lock_file)
    if isinstance(lock_data, dict):
        picks_map = lock_data.get('picks') if isinstance(lock_data.get('picks'), dict) else lock_data
        if isinstance(picks_map, dict):
            for email, picks in picks_map.items():
                if email not in recovered:
                    recovered[email] = _normalize_list(picks, length)
    # 3. Live JSON (in case some submissions never logged for some reason)
    live = _safe_load_json(json_file)
    if isinstance(live, dict):
        for email, picks in live.items():
            if email not in recovered:
                recovered[email] = _normalize_list(picks, length)
    return recovered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', help='Write aggregated JSON to this path')
    ap.add_argument('--csv', help='Write a combined CSV to this path')
    ap.add_argument('--include-empty', action='store_true', help='Include emails whose picks are entirely blank')
    args = ap.parse_args()

    result = {}

    # Thursday direct
    thu_map = {}
    thu_raw = _safe_load_json(THU_JSON)
    if isinstance(thu_raw, dict):
        for email, picks in thu_raw.items():
            thu_map[email.lower()] = _normalize_list(picks, THU_LEN)
    result['Thu'] = thu_map

    # Friday/Saturday/Sunday via recovery pipeline
    result['Fri'] = recover_day(*FRI_INFO)
    result['Sat'] = recover_day(*SAT_INFO)
    result['Sun'] = recover_day(*SUN_INFO)

    # Build union of emails
    all_emails = set(result['Thu'].keys()) | set(result['Fri'].keys()) | set(result['Sat'].keys()) | set(result['Sun'].keys())

    # Optionally filter out blank-only rows per day for CSV output
    def non_blank(picks: List[str]) -> bool:
        return any(bool(p) for p in picks)

    summary = {
        'ok': True,
        'counts': { d: len(v) for d, v in result.items() },
        'emailsTotalUnion': len(all_emails),
        'days': result
    }

    if args.out:
        out_path = pathlib.Path(args.out)
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with out_path.open('w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2)
            print(f"[written] {out_path}")
        except Exception as e:
            print(f"[error] failed writing {out_path}: {e}", file=sys.stderr)

    if args.csv:
        csv_path = pathlib.Path(args.csv)
        try:
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            with csv_path.open('w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                # Determine max picks length across days for uniformity (or just use per-day variable sets)
                writer.writerow(['day','email','pick_index','pick'])
                for day in ['Thu','Fri','Sat','Sun']:
                    length = { 'Thu': THU_LEN, 'Fri': FRI_LEN, 'Sat': SAT_LEN, 'Sun': SUN_LEN }[day]
                    day_map = result[day]
                    for email, picks in sorted(day_map.items()):
                        if not args.include_empty and not non_blank(picks):
                            continue
                        for i, val in enumerate(picks):
                            writer.writerow([day, email, i+1, val])
            print(f"[written] {csv_path}")
        except Exception as e:
            print(f"[error] failed writing {csv_path}: {e}", file=sys.stderr)

    # Always print JSON summary to stdout (even if also wrote file)
    json.dump(summary, sys.stdout, indent=2)
    print()

if __name__ == '__main__':
    main()
