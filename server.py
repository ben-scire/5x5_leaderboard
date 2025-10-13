"""Ultra-minimal Thursday-only leaderboard server (fully cleaned version)."""
"""Ultra-minimal Thursday-only leaderboard server (fully cleaned version)."""
from flask import Flask, jsonify, send_from_directory, request
import time, os, json, pathlib

VERSION = 'week-multi-18'  # Sunday: set first 7 winners + auto NYJ backfill for missing Game 0 picks
# Always treat Saturday JSON snapshot as authoritative; ignore CSV log auto-rebuilds.
FORCE_SATURDAY_JSON = True  # previously env-driven; now permanently enabled
RUNTIME_FORCE_SATURDAY_JSON = True  # runtime flag also locked on so reload logic always prefers JSON

# Final outcomes for the single Thursday game
RESULTS = ['NYG', 'OVER', 'YES']  # Thursday: spread winner, total, prop
# Friday final winners (spread picks): index aligned with FRIDAY_LABELS
FRIDAY_RESULTS = ['USF', 'WASH']
# Saturday results placeholder (filled when games final). Length = 6 games
SATURDAY_RESULTS = [
    'OHIO STATE',   # Game 1 final (Ohio State covers -15.5)
    'MISSOURI',     # Game 2 final (Missouri covers +3.5 vs Alabama)
    'INDIANA',      # Game 3 final (Indiana (+7.5) covers; replaces prior OREGON)
    'TEXAS',        # Game 4 final (Texas covers -2.5)
    'GEORGIA',      # Game 5 final (Georgia covers -4.5)
    'BYU'           # Game 6 final (BYU covers -2.5)
]
# Sunday results (8 games) – first 7 finals entered, last game still pending.
# Order aligns with SUNDAY_LABELS defined later in the file.
# Winners provided by user: NYJ, PIT, MIA, LAR, NE, SEA, TB; last game open.
SUNDAY_RESULTS = [
    'NYJ',  # Game 0 DEN @ NYJ
    'PIT',  # Game 1 CLE @ PIT
    'MIA',  # Game 2 LAC @ MIA
    'NE',   # Game 3 NE @ NO
    'LAR',  # Game 4 LAR @ BAL
    'SEA',  # Game 5 SEA @ JAX
    'TB',   # Game 6 SF @ TB
    None    # Game 7 DET @ KC (pending)
]

# Authoritative Thursday picks now fully external in data/picks/thursday_picks.json (no embedded fallback)
DATA_OVERRIDE_PATH = pathlib.Path('data/picks/thursday_picks.json')
def _load_thursday():
    try:
        if DATA_OVERRIDE_PATH.exists():
            with DATA_OVERRIDE_PATH.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                cleaned = {}
                for k,v in data.items():
                    if isinstance(v, list) and len(v) == len(RESULTS):
                        cleaned[k.lower()] = [str(x).strip().upper() for x in v]
                return cleaned
    except Exception:
        pass
    return {}

HARD_PICKS = _load_thursday()
if not HARD_PICKS:
    # Fallback embedded picks only if JSON missing/empty (ensures historical Thursday data still available)
    HARD_PICKS = {
        "kylejkz11@gmail.com": ["NYG", "OVER", "YES"],
        "max1solov@gmail.com": ["NYG", "OVER", "YES"],
        "samuel.lehman3337@gmail.com": ["PHI", "OVER", "YES"],
        "shawnscottcarl@gmail.com": ["PHI", "OVER", "YES"],
        "finsmaniac1551@gmail.com": ["PHI", "OVER", "NO"],
        "jakelehman100@gmail.com": ["NYG", "OVER", "YES"],
        "hankrudden@yahoo.com": ["NYG", "UNDER", "NO"],
        "scire.ben@gmail.com": ["NYG", "OVER", "YES"],
        "williamjabbott22@gmail.com": ["PHI", "OVER", "YES"],
        "timjbohlman@gmail.com": ["NYG", "OVER", "YES"],
        "goodnoughdylan@gmail.com": ["NYG", "UNDER", "YES"],
        "jaked9577@yahoo.com": ["PHI", "OVER", "YES"],
        "sam.scire@hotmail.com": ["PHI", "OVER", "YES"],
        "soligonaustin@outlook.com": ["PHI", "OVER", "YES"],
        "amacdonald171@gmail.com": ["PHI", "OVER", "YES"],
        "jlindsey3428@gmail.com": ["NYG", "OVER", "YES"],
        "wyaggy3@gmail.com": ["PHI", "UNDER", "YES"]
    }
    SOURCE = 'embedded_fallback'
else:
    SOURCE = 'file'

def _aggregate_all_users():
    base = set(HARD_PICKS.keys())
    # Friday/Saturday picks dicts may not yet be defined; guard via globals()
    if 'FRIDAY_PICKS' in globals():
        base.update(FRIDAY_PICKS.keys())
    if 'SATURDAY_PICKS' in globals():
        base.update(SATURDAY_PICKS.keys())
    if 'SUNDAY_PICKS' in globals():
        base.update(SUNDAY_PICKS.keys())
    return sorted(base)

ALL_USERS = _aggregate_all_users()

def _refresh_all_users():
    global ALL_USERS
    ALL_USERS = _aggregate_all_users()

# ---- PIN system (simple 4-digit per email) ----
PINS_FILE = pathlib.Path('data/picks/pins.json')
ALLOWED_EMAILS_FILE = pathlib.Path('data/allowed_emails.json')
ACTIVE_EMAILS_FILE = pathlib.Path('data/active_emails.json')  # optional narrower roster for this week

def _load_allowed_emails():
    """Union of Thursday core users + allowed_emails.json; optionally narrowed by active_emails.json."""
    emails = set(ALL_USERS)
    try:
        if ALLOWED_EMAILS_FILE.exists():
            with ALLOWED_EMAILS_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                for e in data:
                    if isinstance(e, str) and '@' in e:
                        emails.add(e.strip().lower())
    except Exception:
        pass
    # Apply active filter if present
    try:
        if ACTIVE_EMAILS_FILE.exists():
            with ACTIVE_EMAILS_FILE.open('r', encoding='utf-8') as f:
                active = json.load(f)
            if isinstance(active, list) and active:
                active_set = { a.strip().lower() for a in active if isinstance(a,str) }
                emails = emails.intersection(active_set)
    except Exception:
        pass
    return sorted(emails)

def _load_or_create_pins(emails):
    # Return dict email->pin (4-digit string). Create if missing or missing emails.
    existing = {}
    if PINS_FILE.exists():
        try:
            with PINS_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k,v in data.items():
                    if isinstance(k,str) and isinstance(v,str) and len(v)==4 and v.isdigit():
                        existing[k.lower()] = v
        except Exception:
            existing = {}
    changed = False
    import random
    used = set(existing.values())
    for e in emails:
        if e not in existing:
            # generate unique pin
            for _ in range(20):
                pin = f"{random.randint(0,9999):04d}"
                if pin not in used:
                    break
            existing[e] = pin
            used.add(pin)
            changed = True
    if changed:
        try:
            PINS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with PINS_FILE.open('w', encoding='utf-8') as f:
                json.dump(existing, f, indent=2)
        except Exception:
            pass
    return existing

ALLOWED_EMAILS = _load_allowed_emails()
PIN_MAP = _load_or_create_pins(ALLOWED_EMAILS)
# If pins file had entries for emails now inactive, drop them from runtime map (do not rewrite file automatically).
PIN_MAP = { k:v for k,v in PIN_MAP.items() if k in ALLOWED_EMAILS }

def _check_pin(email: str, pin: str):
    return PIN_MAP.get(email.lower()) == pin
TOTAL_POSSIBLE = len(RESULTS) + len(FRIDAY_RESULTS) + len(SATURDAY_RESULTS) + len(SUNDAY_RESULTS)

app = Flask(__name__, static_folder='.', static_url_path='')

# --- Cache control: prevent stale HTML on mobile Safari / iOS ---
# Strategy:
# 1. All HTML responses get no-store headers so updates are always fetched.
# 2. Static assets (css/js) keep cacheable names but we append a ?v=VERSION query in HTML.
#    When you change VERSION constant above, bump ASSET_TAG below or directly edit HTML query strings.

@app.after_request
def _add_cache_headers(resp):
    ct = (resp.mimetype or '').lower()
    # Strong no-cache for HTML and JSON API responses to avoid stale schedule/picks data in browsers or CDN.
    if 'text/html' in ct or 'application/json' in ct:
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
    return resp

# --- Simple persistent storage for Friday picks (new feature) ---
FRIDAY_FILE = pathlib.Path('data/picks/friday_picks.json')
FRIDAY_CSV_LOG = pathlib.Path('data/picks/friday_picks_log.csv')
FRIDAY_LOCK_FILE = pathlib.Path('data/picks/friday_locked.json')
FRIDAY_LOCK_STATUS = pathlib.Path('data/picks/friday_lock_status.json')
FRIDAY_SEED_CSV = pathlib.Path('data/picks/Fri_Picks.csv')  # new: seed file provided by user
FRIDAY_LABELS = [
    'NCAAF: USF +1.5 @ UNT (pick team)',
    'NCAAF: Rutgers +10.5 @ WASH (pick team)'
]

# Static Friday schedule (live board) with ESPN event IDs.
# Lines chosen to match displayed pick lines (not necessarily latest market line).
FRIDAY_SCHEDULE = [
    # Both games explicitly dated 2025-10-10 UTC start approximations; sport metadata included.
    {
        'sport': 'NCAAF',
        'eventId': '401762481',
        'away': 'South Florida', 'awayAbbr': 'USF',
        'home': 'North Texas',   'homeAbbr': 'UNT',
        'lineHome': -1.5,
        'total': None,
        'start': '2025-10-10T23:30:00Z'
    },
    {
        'sport': 'NCAAF',
        'eventId': '401752862',
        'away': 'Rutgers',    'awayAbbr': 'RUT',
        'home': 'Washington', 'homeAbbr': 'WASH',
        'lineHome': -10.5,
        'total': None,
        'start': '2025-10-10T23:59:00Z'  # normalized to same calendar date 10/10 UTC late evening
    }
]

# ------------------ Saturday (new) ------------------
SATURDAY_LABELS = [
    'NCAAF: Ohio St -15.5 @ Illinois (pick team)',
    'NCAAF: Alabama -3.5 @ Missouri (pick team)',
    'NCAAF: Indiana +7.5 @ Oregon (pick team)',
    'NCAAF: Oklahoma +2.5 @ Texas (pick team)',
    'NCAAF: Georgia -4.5 @ Auburn (pick team)',
    'NCAAF: BYU -2.5 @ Arizona (pick team)'
]

# For now eventIds unknown/placeholder; can be updated later with real ESPN IDs.
# lineHome semantics: negative => home favored by abs(line); positive => away favored by that amount.
SATURDAY_SCHEDULE = [
    # Added real ESPN event IDs for the two noon (16:00Z) games so live fetch works immediately.
    { 'sport':'NCAAF', 'eventId': '401752865', 'away':'Ohio State', 'awayAbbr':'OHST', 'home':'Illinois', 'homeAbbr':'ILL', 'lineHome': +15.5, 'total': None, 'start':'2025-10-11T16:00:00Z' },
    { 'sport':'NCAAF', 'eventId': '401752734', 'away':'Alabama', 'awayAbbr':'ALA', 'home':'Missouri', 'homeAbbr':'MIZ', 'lineHome': +3.5, 'total': None, 'start':'2025-10-11T16:00:00Z' },
    # Remaining games now updated with ESPN event IDs for live tracking.
    { 'sport':'NCAAF', 'eventId': '401752870', 'away':'Indiana', 'awayAbbr':'IND', 'home':'Oregon', 'homeAbbr':'ORE', 'lineHome': -7.5, 'total': None, 'start':'2025-10-11T19:30:00Z' },
    { 'sport':'NCAAF', 'eventId': '401752736', 'away':'Oklahoma', 'awayAbbr':'OKLA', 'home':'Texas', 'homeAbbr':'TEX', 'lineHome': -2.5, 'total': None, 'start':'2025-10-11T19:30:00Z' },
    { 'sport':'NCAAF', 'eventId': '401752867', 'away':'Georgia', 'awayAbbr':'UGA', 'home':'Auburn', 'homeAbbr':'AUB', 'lineHome': +4.5, 'total': None, 'start':'2025-10-11T23:30:00Z' },  # Verify 401752867 (ABC 23:30Z)
    { 'sport':'NCAAF', 'eventId': '401756916', 'away':'BYU', 'awayAbbr':'BYU', 'home':'Arizona', 'homeAbbr':'ARIZ', 'lineHome': +2.5, 'total': None, 'start':'2025-10-12T00:00:00Z' }
]

# Saturday storage paths
SATURDAY_FILE = pathlib.Path('data/picks/saturday_picks.json')  # Saturday storage paths (JSON snapshot is the ONLY authoritative source now)
SATURDAY_LOCK_FILE = pathlib.Path('data/picks/saturday_locked.json')
SATURDAY_LOCK_STATUS = pathlib.Path('data/picks/saturday_lock_status.json')

def _load_saturday():
    if SATURDAY_FILE.exists():
        try:
            with SATURDAY_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                out = {}
                for email, picks in data.items():
                    if isinstance(picks, list):
                        adj = picks[:len(SATURDAY_LABELS)]
                        while len(adj) < len(SATURDAY_LABELS):
                            adj.append('')
                        out[email] = [p.strip().upper() for p in adj]
                return out
        except Exception:
            return {}
    return {}

def _save_saturday(data: dict):
    try:
        SATURDAY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SATURDAY_FILE.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False

def _append_saturday_csv(email: str, picks: list):
    # Deprecated: CSV logging disabled (JSON only). Kept as no-op for backward compatibility.
    return

def _is_saturday_locked():
    return SATURDAY_LOCK_FILE.exists()

def _load_saturday_locked():
    if SATURDAY_LOCK_FILE.exists():
        try:
            with SATURDAY_LOCK_FILE.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _write_saturday_locked(snapshot: dict):
    try:
        SATURDAY_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SATURDAY_LOCK_FILE.open('w', encoding='utf-8') as f:
            json.dump({ 'lockedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'picks': snapshot }, f, indent=2)
        with SATURDAY_LOCK_STATUS.open('w', encoding='utf-8') as f:
            json.dump({ 'locked': True, 'lockedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) }, f)
        return True
    except Exception:
        return False

def _load_saturday_lock_status():
    if SATURDAY_LOCK_STATUS.exists():
        try:
            with SATURDAY_LOCK_STATUS.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return { 'locked': True }
    return { 'locked': False }

SATURDAY_PICKS = _load_saturday()

def _enforce_full_saturday():
    """Ensure every Saturday picks list is exactly len(SATURDAY_LABELS)."""
    global SATURDAY_PICKS
    changed = False
    norm = {}
    for email, picks in SATURDAY_PICKS.items():
        if not isinstance(picks, list):
            picks = []
        if len(picks) < len(SATURDAY_LABELS):
            picks = picks + [''] * (len(SATURDAY_LABELS)-len(picks))
            changed = True
        elif len(picks) > len(SATURDAY_LABELS):
            picks = picks[:len(SATURDAY_LABELS)]
            changed = True
        norm[email] = picks
    SATURDAY_PICKS = norm
    if changed:
        try: _save_saturday(SATURDAY_PICKS)
        except Exception: pass

_enforce_full_saturday()

# --- Server-side backfill: ensure specified users have at least first two Saturday picks visible.
_SAT_BACKFILL_TARGETS = [
    'finsmaniac1551@gmail.com',
    'jlindsey3428@gmail.com',
    'samuel.lehman3337@gmail.com'
]
def _apply_saturday_backfill():
    changed=False
    for em in _SAT_BACKFILL_TARGETS:
        picks = SATURDAY_PICKS.get(em)
        if not picks:
            # create blank row then rely on client or manual later
            SATURDAY_PICKS[em] = ['']*len(SATURDAY_LABELS)
            picks = SATURDAY_PICKS[em]
            changed=True
        # If first two are blank but user has later picks or result finals known, leave blanks (means no submission) – here we only ensure list exists.
        if len(picks) < len(SATURDAY_LABELS):
            while len(picks) < len(SATURDAY_LABELS): picks.append('')
            changed=True
    if changed:
        try: _save_saturday(SATURDAY_PICKS)
        except Exception: pass
_apply_saturday_backfill()

# --- New: force-fill first two Saturday games for target users if still blank ---
def _force_first_two_targets():
    """If any target user still has blank picks for games 0 or 1, attempt to pull from snapshot;
    if snapshot also blank, leave untouched (avoids fabricating picks)."""
    if not SATURDAY_FILE.exists():
        return False
    try:
        with SATURDAY_FILE.open('r', encoding='utf-8') as f:
            snapshot = json.load(f)
    except Exception:
        return False
    if not isinstance(snapshot, dict):
        return False
    changed = False
    for em in _SAT_BACKFILL_TARGETS:
        cur = SATURDAY_PICKS.get(em)
        snap = snapshot.get(em)
        if not isinstance(cur, list):
            cur = ['']*len(SATURDAY_LABELS)
            SATURDAY_PICKS[em] = cur
            changed = True
        if snap and isinstance(snap, list):
            # normalize snapshot length
            snap_norm = snap[:len(SATURDAY_LABELS)] + ['']*max(0, len(SATURDAY_LABELS)-len(snap))
            # For first two indices only
            for i in (0,1):
                if i < len(cur) and not cur[i] and snap_norm[i]:
                    cur[i] = str(snap_norm[i]).strip().upper()
                    changed = True
        # Ensure list length integrity
        if len(cur) < len(SATURDAY_LABELS):
            cur.extend(['']*(len(SATURDAY_LABELS)-len(cur)))
            changed = True
    if changed:
        _save_saturday(SATURDAY_PICKS)
        _refresh_all_users()
    return changed

_force_first_two_targets()

# --- CSV authoritative rebuild (new) ---
# Saturday should now derive its live/authoritative state from the CSV log (latest row per email),
# not from the JSON snapshot. We still keep the JSON snapshot for durability / restart speed, but
# whenever the CSV log changes we rebuild SATURDAY_PICKS in-memory from it.
## Removed legacy Saturday CSV rebuild logic (JSON-only authoritative mode).

# --- Hot reload support (mtime-based) for Saturday picks ---
_SATURDAY_FILE_MTIME = SATURDAY_FILE.stat().st_mtime if SATURDAY_FILE.exists() else None

# Post-definition startup sync: if CSV present, rebuild picks immediately.
try:
    # JSON authoritative bootstrap
    if not SATURDAY_PICKS and SATURDAY_FILE.exists():
        data = _load_saturday()
        if isinstance(data, dict) and data:
            SATURDAY_PICKS = data
            _enforce_full_saturday()
except Exception:
    pass

def _maybe_reload_saturday():
    """Reload Saturday picks if JSON snapshot changed (JSON-only mode)."""
    global SATURDAY_PICKS, _SATURDAY_FILE_MTIME
    try:
        if SATURDAY_FILE.exists():
            json_mtime = SATURDAY_FILE.stat().st_mtime
            if _SATURDAY_FILE_MTIME is None or json_mtime > _SATURDAY_FILE_MTIME:
                data = _load_saturday()
                if isinstance(data, dict) and data:
                    SATURDAY_PICKS = data
                    _enforce_full_saturday()
                _SATURDAY_FILE_MTIME = json_mtime
                _refresh_all_users()
                return True
    except Exception:
        pass
    return False

# --- Repair helper: merge any non-blank picks from snapshot file into in-memory SATURDAY_PICKS
def _repair_saturday_from_file():
    if not SATURDAY_FILE.exists():
        return False
    try:
        with SATURDAY_FILE.open('r', encoding='utf-8') as f:
            snapshot = json.load(f)
        if not isinstance(snapshot, dict):
            return False
        changed=False
        for email, picks in snapshot.items():
            if not isinstance(picks, list):
                continue
            adj = picks[:len(SATURDAY_LABELS)]
            while len(adj) < len(SATURDAY_LABELS): adj.append('')
            if email not in SATURDAY_PICKS:
                SATURDAY_PICKS[email] = [p.strip().upper() for p in adj]
                changed=True
                continue
            cur = SATURDAY_PICKS[email]
            if len(cur) < len(SATURDAY_LABELS):
                cur += [''] * (len(SATURDAY_LABELS)-len(cur))
                changed=True
            for i,val in enumerate(adj):
                if val and not cur[i]:
                    cur[i] = val.strip().upper()
                    changed=True
        # After generic repair, force-fill first two for targets (may already be handled above but ensure).
        if _force_first_two_targets():
            changed = True
        if changed:
            _save_saturday(SATURDAY_PICKS)
            _refresh_all_users()
        return changed
    except Exception:
        return False

# ---- Per-game locking (Saturday) ----
# New granular locking replaces the prior whole-day locking workflow for Saturday.
# A game is considered locked if either (a) it has been manually locked by the admin
# or (b) the current time is past (>=) the scheduled kickoff time. Manual unlocks
# cannot override kickoff-based automatic locks.
SATURDAY_GAME_LOCKS_FILE = pathlib.Path('data/picks/saturday_game_locks.json')

def _load_saturday_game_locks():
    if SATURDAY_GAME_LOCKS_FILE.exists():
        try:
            with SATURDAY_GAME_LOCKS_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data.get('manualLocks', {}) if isinstance(data.get('manualLocks', {}), dict) else {}
        except Exception:
            return {}
    return {}

def _save_saturday_game_locks(locks: dict):
    try:
        SATURDAY_GAME_LOCKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = { 'manualLocks': locks, 'updated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) }
        with SATURDAY_GAME_LOCKS_FILE.open('w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)
        return True
    except Exception:
        return False

def _parse_iso_utc(ts: str):
    if not ts or not isinstance(ts, str):
        return None
    # Accept forms like 2025-10-11T16:00:00Z
    try:
        if ts.endswith('Z'):
            ts = ts[:-1]
        # Basic split
        date_part, time_part = ts.split('T')
        y,m,d = [int(x) for x in date_part.split('-')]
        hh,mm,ss = [int(x) for x in time_part.split(':')]
        import calendar
        return calendar.timegm((y,m,d,hh,mm,ss,0,0,0))
    except Exception:
        return None

_SATURDAY_MANUAL_LOCKS = _load_saturday_game_locks()  # keys are str(indices) -> bool

def _is_saturday_game_locked(index: int):
    """Locking disabled: always returns False so users' picks always persist/update."""
    return False

def _saturday_effective_locks():
    # All games unlocked; reflect that explicitly for clients.
    return [{ 'index': i, 'manualLocked': False, 'started': False, 'effectiveLocked': False, 'start': g.get('start') } for i,g in enumerate(SATURDAY_SCHEDULE)]

def _seed_friday_from_csv():
    """If Fri_Picks.csv exists, load it (email,pick1,pick2) into initial FRIDAY_PICKS before JSON overrides.
    Existing friday_picks.json (if present) still persists subsequent submissions; CSV only seeds once at startup.
    """
    if not FRIDAY_SEED_CSV.exists():
        return {}
    seeded = {}
    try:
        with FRIDAY_SEED_CSV.open('r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        if not lines:
            return {}
        header = [h.strip().lower() for h in lines[0].split(',')]
        # Expect at least: email,pick1,pick2
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 1 + len(FRIDAY_LABELS):
                continue
            email = parts[0].lower()
            picks = [p.upper() for p in parts[1:1+len(FRIDAY_LABELS)]]
            # Normalize abbreviations allowed: USF/UNT/RUT/WASH
            normalized = []
            for p in picks:
                np = p
                if p in ('SOUTH FLORIDA','USF'): np = 'USF'
                elif p in ('NORTH TEXAS','NT','UNT'): np = 'UNT'
                elif p in ('RUTGERS','RUT'): np = 'RUT'
                elif p in ('WASHINGTON','UW','WASH'): np = 'WASH'
                normalized.append(np)
            seeded[email] = normalized
        return seeded
    except Exception:
        return {}

def _load_friday():
    if FRIDAY_FILE.exists():
        try:
            with FRIDAY_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                # Normalize to list of same length as labels
                out = {}
                for email, picks in data.items():
                    if isinstance(picks, list):
                        adj = picks[:len(FRIDAY_LABELS)]
                        while len(adj) < len(FRIDAY_LABELS):
                            adj.append('')
                        out[email] = [p.strip().upper() for p in adj]
                return out
        except Exception:
            return {}
    return {}

def _save_friday(data: dict):
    try:
        FRIDAY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with FRIDAY_FILE.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False
def _append_friday_csv(email: str, picks: list):
    """Append a single submission row to the CSV log (best-effort, never raises)."""
    try:
        FRIDAY_CSV_LOG.parent.mkdir(parents=True, exist_ok=True)
        is_new = not FRIDAY_CSV_LOG.exists()
        with FRIDAY_CSV_LOG.open('a', encoding='utf-8') as f:
            if is_new:
                f.write('ts_iso,email,' + ','.join([f'pick{i+1}' for i in range(len(FRIDAY_LABELS))]) + '\n')
            ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
            row = [ts, email] + picks
            safe = [c.replace('\n',' ').replace('\r',' ').replace(',',' ') for c in row]
            f.write(','.join(safe) + '\n')
    except Exception:
        pass  # logging failure is non-fatal

def _is_friday_locked():
    return FRIDAY_LOCK_FILE.exists()

def _load_friday_locked():
    if FRIDAY_LOCK_FILE.exists():
        try:
            with FRIDAY_LOCK_FILE.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _snapshot_latest_from_log():
    """Read the CSV log and produce a dict of latest picks per email (overwriting earlier rows)."""
    if not FRIDAY_CSV_LOG.exists():
        # Fallback to in-memory
        return FRIDAY_PICKS.copy()
    latest = {}
    try:
        with FRIDAY_CSV_LOG.open('r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        if not lines:
            return FRIDAY_PICKS.copy()
        header = lines[0].split(',')
        # Expect: ts_iso,email,pick1,pick2,...
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split(',')
            if len(parts) < 2 + len(FRIDAY_LABELS):
                continue
            ts = parts[0]
            email = parts[1].strip().lower()
            picks = [p.strip().upper() for p in parts[2:2+len(FRIDAY_LABELS)]]
            latest[email] = picks
        return latest
    except Exception:
        return FRIDAY_PICKS.copy()

def _write_friday_locked(snapshot: dict):
    try:
        FRIDAY_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with FRIDAY_LOCK_FILE.open('w', encoding='utf-8') as f:
            json.dump({ 'lockedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'picks': snapshot }, f, indent=2)
        with FRIDAY_LOCK_STATUS.open('w', encoding='utf-8') as f:
            json.dump({ 'locked': True, 'lockedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) }, f)
        return True
    except Exception:
        return False

def _load_friday_lock_status():
    if FRIDAY_LOCK_STATUS.exists():
        try:
            with FRIDAY_LOCK_STATUS.open('r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return { 'locked': True }
    return { 'locked': False }

def _merge_seed_into_friday(existing: dict):
    """Merge any missing emails from the CSV seed into existing picks (without overwriting current picks)."""
    seed = _seed_friday_from_csv()
    if not seed:
        return existing, False
    changed = False
    for email, picks in seed.items():
        if email not in existing:
            existing[email] = picks
            changed = True
    if changed:
        _save_friday(existing)
    return existing, changed

_seeded_csv = _seed_friday_from_csv()
FRIDAY_PICKS = _seeded_csv if _seeded_csv else _load_friday()  # initial load
# Always perform a merge to ensure any newly added CSV rows appear even after prior submissions
FRIDAY_PICKS, _merged = _merge_seed_into_friday(FRIDAY_PICKS)

@app.route('/api/admin/friday/seed', methods=['POST'])
def admin_friday_seed():
    """Admin endpoint: re-run CSV merge to backfill any missing rows from Fri_Picks.csv."""
    global FRIDAY_PICKS
    before = len(FRIDAY_PICKS)
    FRIDAY_PICKS, changed = _merge_seed_into_friday(FRIDAY_PICKS)
    after = len(FRIDAY_PICKS)
    return jsonify({ 'ok': True, 'changed': changed, 'countBefore': before, 'countAfter': after })

@app.route('/api/picks/friday/labels')
def friday_labels():
    return jsonify({ 'ok': True, 'labels': FRIDAY_LABELS })

@app.route('/api/picks/friday/get')
def friday_get():
    email = (request.args.get('email') or '').strip().lower()
    picks = FRIDAY_PICKS.get(email)
    return jsonify({ 'ok': True, 'email': email, 'picks': picks })

@app.route('/api/picks/friday/submit', methods=['POST'])
def friday_submit():
    payload = request.get_json(force=True, silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    picks = payload.get('picks') or []
    pin = str(payload.get('pin') or '').strip()
    if _is_friday_locked():
        return jsonify({ 'ok': False, 'error': 'locked' }), 403
    if not email:
        return jsonify({ 'ok': False, 'error': 'email_required' }), 400
    if not isinstance(picks, list) or len(picks) != len(FRIDAY_LABELS):
        return jsonify({ 'ok': False, 'error': 'invalid_picks_length' }), 400
    if email not in ALLOWED_EMAILS:
        return jsonify({ 'ok': False, 'error': 'unauthorized_email' }), 403
    if not _check_pin(email, pin):
        return jsonify({ 'ok': False, 'error': 'invalid_pin' }), 403
    norm = [str(p or '').strip().upper() for p in picks]
    FRIDAY_PICKS[email] = norm
    if not _save_friday(FRIDAY_PICKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    _append_friday_csv(email, norm)
    return jsonify({ 'ok': True, 'saved': True })

@app.route('/api/picks/friday/all')
def friday_all():
    # Monitoring endpoint: list of all submitted Friday picks + counts per selection
    counts = [ {}, {} ]  # one dict per matchup
    for email, picks in FRIDAY_PICKS.items():
        for i, val in enumerate(picks):
            if i >= len(counts):
                break
            if not val:
                continue
            d = counts[i]
            d[val] = d.get(val, 0) + 1
    locked = _is_friday_locked()
    lockedData = _load_friday_locked() if locked else None
    return jsonify({
        'ok': True,
        'labels': FRIDAY_LABELS,
        'totalSubmissions': len(FRIDAY_PICKS),
        'picks': FRIDAY_PICKS,
        'counts': counts,
        'locked': locked,
        'lockedSnapshot': lockedData.get('picks') if lockedData else None,
        'lockedAt': lockedData.get('lockedAt') if lockedData else None
    })

@app.route('/api/picks/friday/status')
def friday_status():
    """Return list of submitted emails and which known Thursday users haven't submitted Friday picks yet."""
    _refresh_all_users()
    submitted = sorted(FRIDAY_PICKS.keys())
    # Use Thursday ALL_USERS as the pool; if override file replaced, ALL_USERS already reflects it.
    missing = [u for u in ALL_USERS if u not in FRIDAY_PICKS]
    return jsonify({ 'ok': True, 'submitted': submitted, 'missing': missing, 'submittedCount': len(submitted), 'missingCount': len(missing), 'locked': _is_friday_locked() })

@app.route('/api/picks/friday/lock', methods=['POST'])
def friday_lock():
    if _is_friday_locked():
        # Already locked: return existing info
        data = _load_friday_locked()
        return jsonify({ 'ok': True, 'alreadyLocked': True, 'lockedAt': data.get('lockedAt'), 'count': len(data.get('picks', {})) })
    snapshot = _snapshot_latest_from_log()
    if not snapshot:
        snapshot = FRIDAY_PICKS.copy()
    if not _write_friday_locked(snapshot):
        return jsonify({ 'ok': False, 'error': 'lock_write_failed' }), 500
    return jsonify({ 'ok': True, 'locked': True, 'count': len(snapshot) })

@app.route('/api/picks/friday/lock/status')
def friday_lock_status():
    st = _load_friday_lock_status()
    if st.get('locked'):
        data = _load_friday_locked()
        st['count'] = len(data.get('picks', {}))
        st['emails'] = sorted(data.get('picks', {}).keys())
    return jsonify({ 'ok': True, **st })

def _csv_escape(val: str):
    if any(c in val for c in [',','"','\n','\r']):
        return '"' + val.replace('"', '""') + '"'
    return val

@app.route('/api/picks/export')
def picks_export():
    """Export current (or locked) picks for a day as CSV. Supports day=Thu or day=Fri."""
    day = (request.args.get('day') or '').strip().lower()
    if day.startswith('thu'):
        # Thursday: authoritative picks are HARD_PICKS (possibly file override)
        header = ['email'] + [f'pick{i+1}' for i in range(len(RESULTS))]
        lines = [','.join(header)]
        for email in sorted(HARD_PICKS.keys()):
            row = [email] + HARD_PICKS[email]
            lines.append(','.join(_csv_escape(str(v)) for v in row))
        csv_data = '\n'.join(lines) + '\n'
        return app.response_class(csv_data, mimetype='text/csv')
    if day.startswith('fri'):
        # If locked, use locked snapshot; else live latest FRIDAY_PICKS
        if _is_friday_locked():
            data = _load_friday_locked().get('picks', {})
        else:
            data = FRIDAY_PICKS
        header = ['email'] + [f'pick{i+1}' for i in range(len(FRIDAY_LABELS))]
        lines = [','.join(header)]
        for email in sorted(data.keys()):
            row = [email] + data[email]
            lines.append(','.join(_csv_escape(str(v)) for v in row))
        csv_data = '\n'.join(lines) + '\n'
        return app.response_class(csv_data, mimetype='text/csv')
    return jsonify({ 'ok': False, 'error': 'unsupported_day' }), 400

@app.route('/api/picks/friday/log')
def friday_log():
    # Return entire CSV log as text (small scale). If large, could stream.
    if not FRIDAY_CSV_LOG.exists():
        return jsonify({ 'ok': True, 'empty': True, 'message': 'no_log' })
    try:
        with FRIDAY_CSV_LOG.open('r', encoding='utf-8') as f:
            content = f.read()
        return app.response_class(content, mimetype='text/csv')
    except Exception as e:
        return jsonify({ 'ok': False, 'error': 'log_read_failed', 'detail': str(e) }), 500

@app.route('/api/picks/friday/log/info')
def friday_log_info():
    """Lightweight metadata about the CSV log so you can monitor without downloading full file."""
    if not FRIDAY_CSV_LOG.exists():
        return jsonify({ 'ok': True, 'exists': False })
    try:
        stat = FRIDAY_CSV_LOG.stat()
        size = stat.st_size
        mtime = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(stat.st_mtime))
        # Count rows cheaply (could be optimized if file grows, fine for small scale)
        with FRIDAY_CSV_LOG.open('r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        rows = max(0, len(lines) - 1) if lines else 0  # exclude header
        return jsonify({ 'ok': True, 'exists': True, 'sizeBytes': size, 'modified': mtime, 'rowCount': rows })
    except Exception as e:
        return jsonify({ 'ok': False, 'error': 'log_info_failed', 'detail': str(e) }), 500

@app.route('/api/picks/friday/log/latest')
def friday_log_latest():
    # Quick JSON variant: last N (default 50) rows
    limit = int(request.args.get('n', '50'))
    if limit < 1: limit = 1
    if limit > 500: limit = 500
    if not FRIDAY_CSV_LOG.exists():
        return jsonify({ 'ok': True, 'rows': [] })
    try:
        with FRIDAY_CSV_LOG.open('r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        if not lines:
            return jsonify({ 'ok': True, 'rows': [] })
        header, *body = lines
        tail = body[-limit:]
        cols = header.split(',')
        rows = []
        for line in tail:
            parts = line.split(',')
            if len(parts) != len(cols):
                continue
            rows.append(dict(zip(cols, parts)))
        return jsonify({ 'ok': True, 'rows': rows, 'count': len(rows) })
    except Exception as e:
        return jsonify({ 'ok': False, 'error': 'log_tail_failed', 'detail': str(e) }), 500

def _norm_team(val: str):
    if not val: return ''
    v = val.strip().upper()
    # Fast path exact matches already canonical
    canonical = {
        'OHIO STATE','MISSOURI','ILLINOIS','ALABAMA','INDIANA','OREGON','OKLAHOMA','TEXAS','GEORGIA','AUBURN','BYU','ARIZONA'
    }
    if v in canonical:
        return v
    # Alias map (tokens only). We split on whitespace and rejoin to limit accidental substring duplication.
    alias = {
        'OHIO':'OHIO', # do not alter
        'OHIO ST':'OHIO STATE',
        'MIZ':'MISSOURI','MIZZOU':'MISSOURI',
        'ILL':'ILLINOIS',
        'ALA':'ALABAMA',
        'IND':'INDIANA',
        'ORE':'OREGON',
        'OKLA':'OKLAHOMA',
        'TEX':'TEXAS',
        'UGA':'GEORGIA',
        'AUB':'AUBURN',
        'ARIZ':'ARIZONA'
    }
    # Additional single-word ESPN-style abbreviations fallback
    if v == 'OHIO ST': return 'OHIO STATE'
    if v == 'MIZ': return 'MISSOURI'
    if v == 'IND': return 'INDIANA'
    # Exact token replacement (preserve ordering of multi-word names)
    parts = v.replace('&',' ').replace('.',' ').split()
    for i,p in enumerate(parts):
        # Reconstruct two-word pattern for "OHIO ST" specifically
        if p == 'OHIO' and i+1 < len(parts) and parts[i+1] == 'ST':
            parts[i] = 'OHIO STATE'
            parts.pop(i+1)
            break
    v2 = ' '.join(alias.get(p, p) for p in parts)
    # Second pass: direct alias if whole string still matches a key
    if v2 in alias:
        v2 = alias[v2]
    return v2

# One-time debug: verify Saturday results normalization (will not raise; prints to console once)
try:
    _sat_norm_check = [(_r, _norm_team(_r)) for _r in SATURDAY_RESULTS]
    if any(a!=b for a,b in _sat_norm_check):
        print('[SAT_DEBUG] Normalization adjusted results:', _sat_norm_check)
    else:
        print('[SAT_DEBUG] Saturday results normalized OK:', _sat_norm_check)
except Exception as _e:
    print('[SAT_DEBUG] normalization self-test failed', _e)

def compute_scores():
    """Return sorted list of scoreboard entries for all users (Thu + Fri + Sat + Sun) with normalization."""
    _maybe_reload_saturday()  # refresh Saturday picks if JSON snapshot changed
    _repair_saturday_from_file()  # merge any non-blank picks that are missing in-memory
    # Ensure Sunday picks reloaded & game0 NYJ backfill applied before scoring
    if 'SUNDAY_PICKS' in globals():
        _maybe_reload_sunday()
        _sunday_backfill_game0_nyj()
    entries = []
    for email in ALL_USERS:
        thu_picks = HARD_PICKS[email]
        thu_answered = sum(1 for p in thu_picks if p)
        thu_score = sum(1 for a, b in zip(thu_picks, RESULTS) if a == b)

        fri_picks = FRIDAY_PICKS.get(email, [])
        fri_answered = sum(1 for p in fri_picks if p)
        fri_score = 0
        for a, b in zip(fri_picks, FRIDAY_RESULTS):
            if b and _norm_team(a) == _norm_team(b):
                fri_score += 1

        sat_picks = SATURDAY_PICKS.get(email, [])
        sat_answered = sum(1 for p in sat_picks if p)
        sat_score = 0
        for a, b in zip(sat_picks, SATURDAY_RESULTS):
            if b and _norm_team(a) == _norm_team(b):
                sat_score += 1

        sun_picks = SUNDAY_PICKS.get(email, []) if 'SUNDAY_PICKS' in globals() else []
        sun_answered = sum(1 for p in sun_picks if p)
        sun_score = 0
        for a, b in zip(sun_picks, SUNDAY_RESULTS):
            if b and _norm_team(a) == _norm_team(b):
                sun_score += 1

        total_score = thu_score + fri_score + sat_score + sun_score
        total_answered = thu_answered + fri_answered + sat_answered + sun_answered
        entries.append({
            'email': email,
            'score': total_score,
            'answered': total_answered,
            'totalPossible': TOTAL_POSSIBLE,
            'perDay': {
                'Thu': { 'score': thu_score, 'answered': thu_answered },
                'Fri': { 'score': fri_score, 'answered': fri_answered },
                'Sat': { 'score': sat_score, 'answered': sat_answered },
                'Sun': { 'score': sun_score, 'answered': sun_answered }
            }
        })
    entries.sort(key=lambda r: (-r['score'], r['answered'], r['email']))
    return entries

@app.route('/api/leaderboard')
def api_leaderboard():
    entries = compute_scores()
    return jsonify({
        'ok': True,
        'dayOrder': ['Thu','Fri','Sat','Sun'],
        'totalPossible': TOTAL_POSSIBLE,
        'entries': entries,
        'generated': int(time.time()*1000)
    })

@app.route('/api/pins/emails')
def api_pins_emails():
    """Return list of selectable emails (no pins)."""
    return jsonify({ 'ok': True, 'emails': ALLOWED_EMAILS, 'version': VERSION, 'partialSaturdayAllowed': True })

@app.route('/api/pins/active', methods=['POST'])
def api_pins_set_active():
    """Admin: overwrite active_emails.json (requires ADMIN_TOKEN if set). Body: { emails: [..] }"""
    token = request.args.get('token') or (request.headers.get('X-Admin-Token'))
    admin_token = os.environ.get('ADMIN_TOKEN')
    if admin_token and token != admin_token:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    payload = request.get_json(force=True, silent=True) or {}
    emails = payload.get('emails')
    if not isinstance(emails, list) or not all(isinstance(e,str) for e in emails):
        return jsonify({ 'ok': False, 'error': 'invalid_emails' }), 400
    # Write file
    try:
        ACTIVE_EMAILS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ACTIVE_EMAILS_FILE.open('w', encoding='utf-8') as f:
            json.dump(sorted({ e.strip().lower() for e in emails if '@' in e }), f, indent=2)
    except Exception as e:
        return jsonify({ 'ok': False, 'error': 'write_failed', 'detail': str(e) }), 500
    # Reload allowed + pins (non-destructive to pins file)
    global ALLOWED_EMAILS, PIN_MAP
    ALLOWED_EMAILS = _load_allowed_emails()
    # Do not regenerate missing pins automatically here; keep existing ones; filter out extras
    PIN_MAP = { k:v for k,v in PIN_MAP.items() if k in ALLOWED_EMAILS }
    return jsonify({ 'ok': True, 'allowed': ALLOWED_EMAILS, 'count': len(ALLOWED_EMAILS) })

@app.route('/api/pins/admin')
def api_pins_admin():
    # Simple safeguard: require query token matching env ADMIN_TOKEN (optional)
    token = request.args.get('token')
    admin_token = os.environ.get('ADMIN_TOKEN')
    if admin_token and token != admin_token:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    # Return full pin map for admin visibility.
    return jsonify({ 'ok': True, 'pins': PIN_MAP })

@app.route('/api/picks/public')
def api_picks_public():
    day = (request.args.get('day') or '').lower()
    if day.startswith('thu'):
        now = int(time.time()*1000)
        return jsonify({
            'ok': True,
            'entries': { email: { 'picks': HARD_PICKS[email], 'ts': now } for email in ALL_USERS }
        })
    if day.startswith('fri'):
        now = int(time.time()*1000)
        # Expose Friday picks (latest submission per email) – already uppercased
        return jsonify({
            'ok': True,
            'entries': { email: { 'picks': picks, 'ts': now } for email, picks in FRIDAY_PICKS.items() }
        })
    if day.startswith('sat'):
        now = int(time.time()*1000)
        _maybe_reload_saturday()
        return jsonify({
            'ok': True,
            'entries': { email: { 'picks': picks, 'ts': now } for email, picks in SATURDAY_PICKS.items() }
        })
    if day.startswith('sun'):
        now = int(time.time()*1000)
        _maybe_reload_sunday(); _sunday_backfill_game0_nyj()
        return jsonify({
            'ok': True,
            'entries': { email: { 'picks': picks, 'ts': now } for email, picks in SUNDAY_PICKS.items() }
        })
    return jsonify({ 'ok': False, 'error': 'unsupported_day' }), 400

@app.route('/api/picks/status/<day_key>')
def picks_status_generic(day_key):
    """Unified status endpoint so frontend can call /api/picks/status/Thu etc.
    Returns submitted + missing arrays similar to existing per-day endpoints.
    """
    dk = (day_key or '').strip().lower()
    _refresh_all_users()
    if dk.startswith('thu'):
        submitted = sorted(HARD_PICKS.keys())
        missing = []
        return jsonify({ 'ok': True, 'day': 'Thu', 'submitted': submitted, 'missing': missing, 'submittedCount': len(submitted), 'missingCount': 0 })
    if dk.startswith('fri'):
        submitted = sorted(FRIDAY_PICKS.keys())
        missing = [u for u in ALL_USERS if u not in FRIDAY_PICKS]
        return jsonify({ 'ok': True, 'day': 'Fri', 'submitted': submitted, 'missing': missing, 'submittedCount': len(submitted), 'missingCount': len(missing) })
    if dk.startswith('sat'):
        _maybe_reload_saturday()
        submitted = sorted(SATURDAY_PICKS.keys())
        missing = [u for u in ALL_USERS if u not in SATURDAY_PICKS]
        return jsonify({ 'ok': True, 'day': 'Sat', 'submitted': submitted, 'missing': missing, 'submittedCount': len(submitted), 'missingCount': len(missing) })
    if dk.startswith('sun'):
        _maybe_reload_sunday(); _sunday_backfill_game0_nyj()
        submitted = sorted(SUNDAY_PICKS.keys())
        missing = [u for u in ALL_USERS if u not in SUNDAY_PICKS]
        return jsonify({ 'ok': True, 'day': 'Sun', 'submitted': submitted, 'missing': missing, 'submittedCount': len(submitted), 'missingCount': len(missing) })
    return jsonify({ 'ok': False, 'error': 'unsupported_day' }), 400

@app.route('/api/debug/thu')
def api_debug_thu():
    entries = compute_scores()[:10]
    slim = [ {k:v for k,v in e.items() if k in ('email','score','answered')} for e in entries ]
    return jsonify({ 'ok': True, 'version': VERSION, 'results': RESULTS, 'sample': slim, 'count': len(ALL_USERS), 'source': SOURCE })

@app.route('/healthz')
def healthz():
    return jsonify({ 'ok': True, 'version': VERSION, 'users': len(ALL_USERS), 'results': RESULTS, 'source': SOURCE })

# -------- Saturday debug / introspection (to diagnose missing games or picks on production) --------
def _saturday_log_info():
    return { 'csvRemoved': True }

@app.route('/api/debug/sat_state')
def debug_sat_state():
    # Reload Saturday JSON if changed
    reloaded = _maybe_reload_saturday()
    # Basic stats
    schedule = [ { 'i': i, 'away': g.get('awayAbbr') or g.get('away'), 'home': g.get('homeAbbr') or g.get('home'), 'eventId': g.get('eventId'), 'start': g.get('start') } for i,g in enumerate(SATURDAY_SCHEDULE) ]
    picks_count = len(SATURDAY_PICKS)
    sample = sorted(list(SATURDAY_PICKS.keys()))[:5]
    missing = [u for u in ALL_USERS if u not in SATURDAY_PICKS][:10]
    # Determine current authoritative source
    source = 'json-forced'
    def _fmt_mtime(path):
        try:
            if path.exists():
                return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(path.stat().st_mtime))
        except Exception:
            return None
        return None
    return jsonify({
        'ok': True,
        'version': VERSION,
        'reloaded': reloaded,
        'forceSaturdayJson': FORCE_SATURDAY_JSON,
        'source': source,
    'csvLogExists': False,
    'csvLogMtime': None,
        'jsonSnapshotMtime': _fmt_mtime(SATURDAY_FILE),
        'scheduleCount': len(SATURDAY_SCHEDULE),
        'schedule': schedule,
        'picksCount': picks_count,
        'sampleEmails': sample,
        'missingSample': missing,
        'csv': _saturday_log_info(),
        'locks': _saturday_effective_locks()
    })

@app.route('/api/schedule')
def api_schedule():
    """Provide schedule JSON consumed by schedule_init.js (Fri + Sat)."""
    days = {
        'Fri': {
            'games': FRIDAY_SCHEDULE,
            'picks': [ { 'label': lbl } for lbl in FRIDAY_LABELS ]
        },
        'Sat': {
            'games': SATURDAY_SCHEDULE,
            'picks': [ { 'label': lbl } for lbl in SATURDAY_LABELS ]
        },
        'Sun': {
            'games': SUNDAY_SCHEDULE,
            'picks': [ { 'label': lbl } for lbl in SUNDAY_LABELS ]
        }
    }
    return jsonify({ 'ok': True, 'version': VERSION, 'days': days })

# -------- Saturday endpoints (mirroring Friday pattern) --------
@app.route('/api/picks/saturday/labels')
def saturday_labels():
    return jsonify({ 'ok': True, 'labels': SATURDAY_LABELS })

@app.route('/api/picks/saturday/get')
def saturday_get():
    email = (request.args.get('email') or '').strip().lower()
    picks = SATURDAY_PICKS.get(email)
    return jsonify({ 'ok': True, 'email': email, 'picks': picks })

@app.route('/api/picks/saturday/submit', methods=['POST'])
def saturday_submit():
    payload = request.get_json(force=True, silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    picks = payload.get('picks') or []
    pin = str(payload.get('pin') or '').strip()
    # Day-level locking retained for backwards compatibility, but granular game
    # locks supersede it. If whole-day lock file exists, reject entire submission.
    if _is_saturday_locked():
        return jsonify({ 'ok': False, 'error': 'day_locked' }), 403
    if not email:
        return jsonify({ 'ok': False, 'error': 'email_required' }), 400
    if not isinstance(picks, list):
        return jsonify({ 'ok': False, 'error': 'invalid_picks_type' }), 400
    # Allow partial submissions: truncate or pad to length; blanks allowed.
    if len(picks) > len(SATURDAY_LABELS):
        picks = picks[:len(SATURDAY_LABELS)]
    if len(picks) < len(SATURDAY_LABELS):
        picks = picks + [''] * (len(SATURDAY_LABELS) - len(picks))
    if email not in ALLOWED_EMAILS:
        return jsonify({ 'ok': False, 'error': 'unauthorized_email' }), 403
    if not _check_pin(email, pin):
        return jsonify({ 'ok': False, 'error': 'invalid_pin' }), 403
    # Preserve existing picks for any game already locked; update only unlocked indices.
    # With locking disabled, accept all submitted values (normalized) directly.
    updated = [str(val or '').strip().upper() for val in picks]
    SATURDAY_PICKS[email] = updated
    if not _save_saturday(SATURDAY_PICKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    _append_saturday_csv(email, SATURDAY_PICKS[email])
    return jsonify({ 'ok': True, 'saved': True, 'lockedGames': [] })

@app.route('/api/picks/saturday/status')
def saturday_status():
    _maybe_reload_saturday()
    _refresh_all_users()
    submitted = sorted(SATURDAY_PICKS.keys())
    missing = [u for u in ALL_USERS if u not in SATURDAY_PICKS]
    return jsonify({ 'ok': True, 'submitted': submitted, 'missing': missing, 'submittedCount': len(submitted), 'missingCount': len(missing), 'locked': _is_saturday_locked(), 'gameLocks': _saturday_effective_locks() })

@app.route('/api/picks/saturday/lock', methods=['POST'])
def saturday_lock():
    if _is_saturday_locked():
        data = _load_saturday_locked()
        return jsonify({ 'ok': True, 'alreadyLocked': True, 'lockedAt': data.get('lockedAt'), 'count': len(data.get('picks', {})) })
    snapshot = SATURDAY_PICKS.copy()
    if not _write_saturday_locked(snapshot):
        return jsonify({ 'ok': False, 'error': 'lock_write_failed' }), 500
    return jsonify({ 'ok': True, 'locked': True, 'count': len(snapshot) })

@app.route('/api/picks/saturday/unlock', methods=['POST'])
def saturday_unlock():
    """Admin: remove Saturday lock files to allow further submissions. Requires ADMIN_TOKEN if set."""
    token = request.args.get('token') or request.headers.get('X-Admin-Token')
    admin_token = os.environ.get('ADMIN_TOKEN')
    if admin_token and token != admin_token:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    # If not locked just return
    if not _is_saturday_locked():
        return jsonify({ 'ok': True, 'alreadyUnlocked': True })
    removed = []
    try:
        if SATURDAY_LOCK_FILE.exists():
            SATURDAY_LOCK_FILE.unlink()
            removed.append(str(SATURDAY_LOCK_FILE))
    except Exception:
        pass
    try:
        if SATURDAY_LOCK_STATUS.exists():
            SATURDAY_LOCK_STATUS.unlink()
            removed.append(str(SATURDAY_LOCK_STATUS))
    except Exception:
        pass
    return jsonify({ 'ok': True, 'unlocked': True, 'removed': removed })

@app.route('/api/picks/saturday/lock/status')
def saturday_lock_status():
    st = _load_saturday_lock_status()
    if st.get('locked'):
        data = _load_saturday_locked()
        st['count'] = len(data.get('picks', {}))
        st['emails'] = sorted(data.get('picks', {}).keys())
    return jsonify({ 'ok': True, **st })

@app.route('/api/picks/saturday/all')
def saturday_all():
    _maybe_reload_saturday()
    counts = [ {} for _ in range(len(SATURDAY_LABELS)) ]
    for email, picks in SATURDAY_PICKS.items():
        for i, val in enumerate(picks):
            if not val: continue
            d = counts[i]
            d[val] = d.get(val, 0) + 1
    locked = _is_saturday_locked()
    lockedData = _load_saturday_locked() if locked else None
    return jsonify({
        'ok': True,
        'labels': SATURDAY_LABELS,
        'totalSubmissions': len(SATURDAY_PICKS),
        'picks': SATURDAY_PICKS,
        'counts': counts,
        'locked': locked,
        'lockedSnapshot': lockedData.get('picks') if lockedData else None,
        'lockedAt': lockedData.get('lockedAt') if lockedData else None,
        'gameLocks': _saturday_effective_locks()
    })

## Removed rebuild/force_json/use_snapshot endpoints: JSON snapshot is always authoritative now.

@app.route('/api/admin/saturday/diagnose')
def admin_saturday_diagnose():
    """Admin: Diagnose Saturday pick completeness.
    Reports which users have blanks for finalized games, counts, and environment/source flags.
    Optional ADMIN_TOKEN gate if configured.
    """
    token = request.args.get('token') or request.headers.get('X-Admin-Token')
    admin_token = os.environ.get('ADMIN_TOKEN')
    if admin_token and token != admin_token:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    # Determine finalized indices
    finalized = [i for i, r in enumerate(SATURDAY_RESULTS) if r]
    blanks = []
    for email, picks in SATURDAY_PICKS.items():
        missing_idx = [i for i in finalized if (i >= len(picks) or not picks[i])]
        if missing_idx:
            blanks.append({ 'email': email, 'blankIndices': missing_idx })
    source = 'json-forced'
    return jsonify({
        'ok': True,
        'forceSaturdayJson': FORCE_SATURDAY_JSON,
        'source': source,
        'finalizedIndices': finalized,
        'usersWithBlanks': len(blanks),
        'blankDetails': blanks,
        'totalUsers': len(SATURDAY_PICKS)
    })

@app.route('/api/admin/saturday/score_debug')
def admin_saturday_score_debug():
    """Return raw vs normalized Saturday picks and results to troubleshoot scoring mismatches.
    Not auth-gated: contains only pick choices already public post-finals.
    """
    _maybe_reload_saturday(); _repair_saturday_from_file()
    data = []
    for email, picks in SATURDAY_PICKS.items():
        raw = picks
        norm = [_norm_team(p) for p in picks]
        res_raw = SATURDAY_RESULTS
        res_norm = [_norm_team(r) for r in SATURDAY_RESULTS]
        score = sum(1 for a,b in zip(norm, res_norm) if b and a==b)
        data.append({ 'email': email, 'raw': raw, 'norm': norm, 'score': score })
    return jsonify({ 'ok': True, 'count': len(data), 'resultsRaw': SATURDAY_RESULTS, 'resultsNorm': [_norm_team(r) for r in SATURDAY_RESULTS], 'entries': data })

@app.route('/api/admin/saturday/force_refill', methods=['POST'])
def admin_saturday_force_refill():
    """Admin: Manually trigger repair + force-fill of first two Saturday games for target users.
    Gated by ADMIN_TOKEN if set. Returns whether any changes were applied and a snapshot of
    the first two picks for each target user after the operation.
    """
    token = request.args.get('token') or request.headers.get('X-Admin-Token')
    admin_token = os.environ.get('ADMIN_TOKEN')
    if admin_token and token != admin_token:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    # Reload & attempt generic repair first, then explicit force for indices 0/1
    _maybe_reload_saturday()
    repaired = _repair_saturday_from_file()
    forced = _force_first_two_targets()
    targets_state = {}
    for em in _SAT_BACKFILL_TARGETS:
        picks = SATURDAY_PICKS.get(em, ['']*len(SATURDAY_LABELS))
        targets_state[em] = picks[:2]
    return jsonify({
        'ok': True,
        'version': VERSION,
        'repairedChanged': repaired,
        'forceFillChanged': forced,
        'changedAny': bool(repaired or forced),
        'targetsFirstTwo': targets_state
    })

@app.route('/api/admin/saturday/override_user', methods=['POST'])
def admin_saturday_override_user():
    """Admin: Hard override a single user's Saturday picks (partial or full).
    Body: { email: str, picks: [..], token?: str }
    Accepts shorter list (pads), longer list (truncates). Requires ADMIN_TOKEN if set.
    Returns before/after for diff visibility.
    """
    token = request.args.get('token') or request.headers.get('X-Admin-Token')
    admin_token = os.environ.get('ADMIN_TOKEN')
    if admin_token and token != admin_token:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    payload = request.get_json(force=True, silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    picks = payload.get('picks')
    if not email:
        return jsonify({ 'ok': False, 'error': 'email_required' }), 400
    if not isinstance(picks, list):
        return jsonify({ 'ok': False, 'error': 'picks_list_required' }), 400
    # Normalize length
    adj = [str(p or '').strip().upper() for p in picks]
    if len(adj) > len(SATURDAY_LABELS):
        adj = adj[:len(SATURDAY_LABELS)]
    if len(adj) < len(SATURDAY_LABELS):
        adj += ['']*(len(SATURDAY_LABELS)-len(adj))
    # Before snapshot
    before = SATURDAY_PICKS.get(email, ['']*len(SATURDAY_LABELS))[:]
    SATURDAY_PICKS[email] = adj
    if not _save_saturday(SATURDAY_PICKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    _refresh_all_users()
    return jsonify({ 'ok': True, 'email': email, 'before': before, 'after': adj })

# --- New Saturday per-game lock endpoints ---
ADMIN_EMAIL = 'scire.ben@gmail.com'  # single admin (adjust if needed)

# ------------------ Sunday (new) ------------------
SUNDAY_LABELS = [
    'NFL: DEN -6.5 @ NYJ (pick team)',            # 9:30 AM ET (London style early game)
    'NFL: CLE +6.5 @ PIT (pick team)',            # 1:00 PM ET
    'NFL: LAC -3.5 @ MIA (pick team)',            # 1:00 PM ET
    'NFL: NE -3.5 @ NO (pick team)',              # 1:00 PM ET
    'NFL: LAR -7.5 @ BAL (pick team)',            # 1:00 PM ET
    'NFL: SEA -1.5 @ JAX (pick team)',            # 1:00 PM ET
    'NFL: SF +3.5 @ TB (pick team)',              # 4:25 PM ET
    'NFL: DET +2.5 @ KC (pick team)'              # 8:20 PM ET
]

# Sunday schedule (home-based line: negative => home favored, positive => away favored)
SUNDAY_SCHEDULE = [
    { 'sport':'NFL', 'eventId': None, 'away':'Denver Broncos', 'awayAbbr':'DEN', 'home':'New York Jets', 'homeAbbr':'NYJ', 'lineHome': +6.5, 'total': None, 'start':'2025-10-12T13:30:00Z' },
    { 'sport':'NFL', 'eventId': None, 'away':'Cleveland Browns', 'awayAbbr':'CLE', 'home':'Pittsburgh Steelers', 'homeAbbr':'PIT', 'lineHome': -6.5, 'total': None, 'start':'2025-10-12T17:00:00Z' },
    { 'sport':'NFL', 'eventId': None, 'away':'Los Angeles Chargers', 'awayAbbr':'LAC', 'home':'Miami Dolphins', 'homeAbbr':'MIA', 'lineHome': +3.5, 'total': None, 'start':'2025-10-12T17:00:00Z' },
    { 'sport':'NFL', 'eventId': None, 'away':'New England Patriots', 'awayAbbr':'NE', 'home':'New Orleans Saints', 'homeAbbr':'NO', 'lineHome': +3.5, 'total': None, 'start':'2025-10-12T17:00:00Z' },
    { 'sport':'NFL', 'eventId': None, 'away':'Los Angeles Rams', 'awayAbbr':'LAR', 'home':'Baltimore Ravens', 'homeAbbr':'BAL', 'lineHome': -7.5, 'total': None, 'start':'2025-10-12T17:00:00Z' },
    { 'sport':'NFL', 'eventId': None, 'away':'Seattle Seahawks', 'awayAbbr':'SEA', 'home':'Jacksonville Jaguars', 'homeAbbr':'JAX', 'lineHome': +1.5, 'total': None, 'start':'2025-10-12T17:00:00Z' },
    { 'sport':'NFL', 'eventId': None, 'away':'San Francisco 49ers', 'awayAbbr':'SF', 'home':'Tampa Bay Buccaneers', 'homeAbbr':'TB', 'lineHome': -3.5, 'total': None, 'start':'2025-10-12T20:25:00Z' },
    { 'sport':'NFL', 'eventId': None, 'away':'Detroit Lions', 'awayAbbr':'DET', 'home':'Kansas City Chiefs', 'homeAbbr':'KC', 'lineHome': -2.5, 'total': None, 'start':'2025-10-13T00:20:00Z' }
]

# Sunday storage
SUNDAY_FILE = pathlib.Path('data/picks/sunday_picks.json')
SUNDAY_CSV_LOG = pathlib.Path('data/picks/sunday_picks_log.csv')
SUNDAY_LOCK_FILE = pathlib.Path('data/picks/sunday_locked.json')  # legacy day-level (not primary)
SUNDAY_LOCK_STATUS = pathlib.Path('data/picks/sunday_lock_status.json')

def _load_sunday():
    if SUNDAY_FILE.exists():
        try:
            with SUNDAY_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                out = {}
                for email, picks in data.items():
                    if isinstance(picks, list):
                        adj = picks[:len(SUNDAY_LABELS)]
                        while len(adj) < len(SUNDAY_LABELS):
                            adj.append('')
                        out[email] = [p.strip().upper() for p in adj]
                return out
        except Exception:
            return {}
    return {}

def _save_sunday(data: dict):
    try:
        SUNDAY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SUNDAY_FILE.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False

def _append_sunday_csv(email: str, picks: list):
    try:
        SUNDAY_CSV_LOG.parent.mkdir(parents=True, exist_ok=True)
        is_new = not SUNDAY_CSV_LOG.exists()
        with SUNDAY_CSV_LOG.open('a', encoding='utf-8') as f:
            if is_new:
                f.write('ts_iso,email,' + ','.join([f'pick{i+1}' for i in range(len(SUNDAY_LABELS))]) + '\n')
            ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
            row = [ts, email] + picks
            safe = [c.replace('\n',' ').replace('\r',' ').replace(',', ' ') for c in row]
            f.write(','.join(safe) + '\n')
    except Exception:
        pass

def _parse_iso_utc_sun(ts: str):
    try:
        if not ts: return None
        if ts.endswith('Z'): ts = ts[:-1]
        date_part, time_part = ts.split('T')
        y,m,d = [int(x) for x in date_part.split('-')]
        hh,mm,ss = [int(x) for x in time_part.split(':')]
        import calendar
        return calendar.timegm((y,m,d,hh,mm,ss,0,0,0))
    except Exception:
        return None

SUNDAY_PICKS = _load_sunday()

# --- Sunday backfill: auto-fill Game 0 (DEN @ NYJ) with NYJ if blank so everyone gets a baseline pick
def _sunday_backfill_game0_nyj():
    try:
        changed = False
        for email, sat in SATURDAY_PICKS.items():  # iterate known active participants
            picks = SUNDAY_PICKS.get(email)
            if not isinstance(picks, list):
                picks = ['']*len(SUNDAY_LABELS)
                SUNDAY_PICKS[email] = picks
                changed = True
            if len(picks) < len(SUNDAY_LABELS):
                picks.extend(['']*(len(SUNDAY_LABELS)-len(picks)))
                changed = True
            # Only backfill if truly blank
            if not picks[0]:
                picks[0] = 'NYJ'
                changed = True
        if changed:
            _save_sunday(SUNDAY_PICKS)
            _refresh_all_users()
        return changed
    except Exception:
        return False

# --- Hot reload support (mtime-based) for Sunday picks ---
_SUNDAY_FILE_MTIME = SUNDAY_FILE.stat().st_mtime if SUNDAY_FILE.exists() else None

def _maybe_reload_sunday():
    global SUNDAY_PICKS, _SUNDAY_FILE_MTIME
    try:
        if not SUNDAY_FILE.exists():
            return False
        mtime = SUNDAY_FILE.stat().st_mtime
        if _SUNDAY_FILE_MTIME is None or mtime > _SUNDAY_FILE_MTIME:
            data = _load_sunday()
            if isinstance(data, dict) and data != SUNDAY_PICKS:
                SUNDAY_PICKS = data
            _SUNDAY_FILE_MTIME = mtime
            _refresh_all_users()
            return True
    except Exception:
        pass
    return False

# Per-game locks Sunday (same semantics as Saturday)
SUNDAY_GAME_LOCKS_FILE = pathlib.Path('data/picks/sunday_game_locks.json')

def _load_sunday_game_locks():
    if SUNDAY_GAME_LOCKS_FILE.exists():
        try:
            with SUNDAY_GAME_LOCKS_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data.get('manualLocks', {}) if isinstance(data.get('manualLocks', {}), dict) else {}
        except Exception:
            return {}
    return {}

def _save_sunday_game_locks(locks: dict):
    try:
        SUNDAY_GAME_LOCKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SUNDAY_GAME_LOCKS_FILE.open('w', encoding='utf-8') as f:
            json.dump({ 'manualLocks': locks, 'updated': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()) }, f, indent=2)
        return True
    except Exception:
        return False

_SUNDAY_MANUAL_LOCKS = _load_sunday_game_locks()

def _is_sunday_game_locked(index: int):
    if str(index) in _SUNDAY_MANUAL_LOCKS and _SUNDAY_MANUAL_LOCKS[str(index)]:
        return True
    if 0 <= index < len(SUNDAY_SCHEDULE):
        start_iso = SUNDAY_SCHEDULE[index].get('start')
        start_epoch = _parse_iso_utc_sun(start_iso)
        if start_epoch is not None and time.time() >= start_epoch:
            return True
    return False

def _sunday_effective_locks():
    out=[]; now_epoch=time.time()
    for i,g in enumerate(SUNDAY_SCHEDULE):
        start_iso = g.get('start'); start_epoch=_parse_iso_utc_sun(start_iso); started = (start_epoch is not None and now_epoch >= start_epoch)
        manual = bool(_SUNDAY_MANUAL_LOCKS.get(str(i)))
        out.append({ 'index': i, 'manualLocked': manual, 'started': started, 'effectiveLocked': manual or started, 'start': start_iso })
    return out

# Sunday endpoints
@app.route('/api/picks/sunday/labels')
def sunday_labels():
    return jsonify({ 'ok': True, 'labels': SUNDAY_LABELS })

@app.route('/api/picks/sunday/get')
def sunday_get():
    email = (request.args.get('email') or '').strip().lower()
    return jsonify({ 'ok': True, 'email': email, 'picks': SUNDAY_PICKS.get(email) })

@app.route('/api/picks/sunday/submit', methods=['POST'])
def sunday_submit():
    payload = request.get_json(force=True, silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    picks = payload.get('picks') or []
    pin = str(payload.get('pin') or '').strip()
    if not email:
        return jsonify({ 'ok': False, 'error': 'email_required' }), 400
    if email not in ALLOWED_EMAILS:
        return jsonify({ 'ok': False, 'error': 'unauthorized_email' }), 403
    if not _check_pin(email, pin):
        return jsonify({ 'ok': False, 'error': 'invalid_pin' }), 403
    if not isinstance(picks, list):
        return jsonify({ 'ok': False, 'error': 'invalid_picks_type' }), 400
    # Allow partial submissions; pad/truncate
    if len(picks) > len(SUNDAY_LABELS): picks = picks[:len(SUNDAY_LABELS)]
    if len(picks) < len(SUNDAY_LABELS): picks = picks + ['']*(len(SUNDAY_LABELS)-len(picks))
    existing = SUNDAY_PICKS.get(email, ['']*len(SUNDAY_LABELS))
    updated=[]
    for idx,val in enumerate(picks):
        if _is_sunday_game_locked(idx):
            updated.append(existing[idx] if idx < len(existing) else '')
        else:
            updated.append(str(val or '').strip().upper())
    SUNDAY_PICKS[email] = updated
    if not _save_sunday(SUNDAY_PICKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    _append_sunday_csv(email, updated)
    return jsonify({ 'ok': True, 'saved': True, 'lockedGames': [i for i in range(len(SUNDAY_LABELS)) if _is_sunday_game_locked(i)] })

@app.route('/api/picks/sunday/status')
def sunday_status():
    _maybe_reload_sunday(); _sunday_backfill_game0_nyj()
    _refresh_all_users()
    submitted = sorted(SUNDAY_PICKS.keys())
    missing = [u for u in ALL_USERS if u not in SUNDAY_PICKS]
    return jsonify({ 'ok': True, 'submitted': submitted, 'missing': missing, 'submittedCount': len(submitted), 'missingCount': len(missing), 'gameLocks': _sunday_effective_locks() })

@app.route('/api/picks/sunday/all')
def sunday_all():
    _maybe_reload_sunday(); _sunday_backfill_game0_nyj()
    counts = [ {} for _ in range(len(SUNDAY_LABELS)) ]
    for email, picks in SUNDAY_PICKS.items():
        for i,val in enumerate(picks):
            if not val: continue
            d = counts[i]; d[val] = d.get(val,0)+1
    return jsonify({ 'ok': True, 'labels': SUNDAY_LABELS, 'totalSubmissions': len(SUNDAY_PICKS), 'picks': SUNDAY_PICKS, 'counts': counts, 'gameLocks': _sunday_effective_locks() })

def _admin_auth_sunday(payload):
    email = (payload.get('email') or '').strip().lower()
    pin = str(payload.get('pin') or '').strip()
    if email != ADMIN_EMAIL: return False, 'not_admin'
    if not _check_pin(email, pin): return False, 'invalid_pin'
    return True, email

@app.route('/api/picks/sunday/game_locks')
def sunday_game_locks():
    return jsonify({ 'ok': True, 'locks': _sunday_effective_locks() })

@app.route('/api/picks/sunday/lock_game', methods=['POST'])
def sunday_lock_game():
    payload = request.get_json(force=True, silent=True) or {}
    ok, err = _admin_auth_sunday(payload)
    if not ok: return jsonify({ 'ok': False, 'error': err }), 403
    try: idx = int(payload.get('index'))
    except Exception: return jsonify({ 'ok': False, 'error': 'invalid_index' }), 400
    if idx < 0 or idx >= len(SUNDAY_LABELS): return jsonify({ 'ok': False, 'error': 'out_of_range' }), 400
    _SUNDAY_MANUAL_LOCKS[str(idx)] = True
    if not _save_sunday_game_locks(_SUNDAY_MANUAL_LOCKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    return jsonify({ 'ok': True, 'locks': _sunday_effective_locks() })

@app.route('/api/picks/sunday/unlock_game', methods=['POST'])
def sunday_unlock_game():
    payload = request.get_json(force=True, silent=True) or {}
    ok, err = _admin_auth_sunday(payload)
    if not ok: return jsonify({ 'ok': False, 'error': err }), 403
    try: idx = int(payload.get('index'))
    except Exception: return jsonify({ 'ok': False, 'error': 'invalid_index' }), 400
    if idx < 0 or idx >= len(SUNDAY_LABELS): return jsonify({ 'ok': False, 'error': 'out_of_range' }), 400
    if _is_sunday_game_locked(idx) and not _SUNDAY_MANUAL_LOCKS.get(str(idx)):
        return jsonify({ 'ok': False, 'error': 'started_auto_lock' }), 409
    _SUNDAY_MANUAL_LOCKS[str(idx)] = False
    if str(idx) in _SUNDAY_MANUAL_LOCKS and not _SUNDAY_MANUAL_LOCKS[str(idx)]:
        _SUNDAY_MANUAL_LOCKS.pop(str(idx), None)
    if not _save_sunday_game_locks(_SUNDAY_MANUAL_LOCKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    return jsonify({ 'ok': True, 'locks': _sunday_effective_locks() })

def _admin_auth(payload):
    email = (payload.get('email') or '').strip().lower()
    pin = str(payload.get('pin') or '').strip()
    if email != ADMIN_EMAIL:
        return False, 'not_admin'
    if not _check_pin(email, pin):
        return False, 'invalid_pin'
    return True, email

@app.route('/api/picks/saturday/game_locks')
def saturday_game_locks():
    return jsonify({ 'ok': True, 'locks': _saturday_effective_locks() })

@app.route('/api/picks/saturday/lock_game', methods=['POST'])
def saturday_lock_game():
    payload = request.get_json(force=True, silent=True) or {}
    ok, err = _admin_auth(payload)
    if not ok:
        return jsonify({ 'ok': False, 'error': err }), 403
    try:
        idx = int(payload.get('index'))
    except Exception:
        return jsonify({ 'ok': False, 'error': 'invalid_index' }), 400
    if idx < 0 or idx >= len(SATURDAY_LABELS):
        return jsonify({ 'ok': False, 'error': 'out_of_range' }), 400
    _SATURDAY_MANUAL_LOCKS[str(idx)] = True
    if not _save_saturday_game_locks(_SATURDAY_MANUAL_LOCKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    return jsonify({ 'ok': True, 'locks': _saturday_effective_locks() })

@app.route('/api/picks/saturday/unlock_game', methods=['POST'])
def saturday_unlock_game():
    payload = request.get_json(force=True, silent=True) or {}
    ok, err = _admin_auth(payload)
    if not ok:
        return jsonify({ 'ok': False, 'error': err }), 403
    try:
        idx = int(payload.get('index'))
    except Exception:
        return jsonify({ 'ok': False, 'error': 'invalid_index' }), 400
    if idx < 0 or idx >= len(SATURDAY_LABELS):
        return jsonify({ 'ok': False, 'error': 'out_of_range' }), 400
    # Cannot unlock after kickoff (auto lock)
    if _is_saturday_game_locked(idx) and not _SATURDAY_MANUAL_LOCKS.get(str(idx)):
        return jsonify({ 'ok': False, 'error': 'started_auto_lock' }), 409
    _SATURDAY_MANUAL_LOCKS[str(idx)] = False
    # Remove key if False to keep file lean
    if str(idx) in _SATURDAY_MANUAL_LOCKS and not _SATURDAY_MANUAL_LOCKS[str(idx)]:
        _SATURDAY_MANUAL_LOCKS.pop(str(idx), None)
    if not _save_saturday_game_locks(_SATURDAY_MANUAL_LOCKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    return jsonify({ 'ok': True, 'locks': _saturday_effective_locks() })

@app.route('/')
def root():
    return send_from_directory('.', 'leaderboard.html')

@app.route('/leaderboard.html')
def leaderboard_page():
    return send_from_directory('.', 'leaderboard.html')

@app.route('/picks.html')
def picks_page():
    return send_from_directory('.', 'picks.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    app.run(host='0.0.0.0', port=port)
