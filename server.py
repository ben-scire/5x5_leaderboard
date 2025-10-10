import json, os, threading, time, csv, hmac, hashlib, base64, secrets
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime, timedelta
try:  # Python 3.9+
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path

APP_ROOT = Path(__file__).parent
DATA_DIR = APP_ROOT / 'data'
DATA_DIR.mkdir(exist_ok=True)
# Unified picks file (per-day structure)
UNIFIED_PICKS_FILE = DATA_DIR / 'picks.json'
SCHEDULE_CSV = DATA_DIR / 'week_schedule.csv'
SCHEDULE_JSON = DATA_DIR / 'schedule.json'
USERS_FILE = DATA_DIR / 'users.json'
ALLOWED_EMAILS_FILE = DATA_DIR / 'allowed_emails.json'
SCHEDULE_LOCK = threading.Lock()
_SCHEDULE_CACHE = { 'version': 0, 'data': None, 'ts': 0 }
LOCK = threading.Lock()

# Auth / token settings
TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 days
SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET') or None
if not SECRET_KEY:
    # Ephemeral key (tokens invalidate on restart). Strongly encourage env var in prod.
    SECRET_KEY = secrets.token_hex(32)

# Phrase map (server-side only)
PHRASE_MAP = {
    'kylejkz11@gmail.com':'kuzzo',
    'max1solov@gmail.com':'max1solov',
    'lukeanastasi5@gmail.com':'staz',
    'samuel.lehman3337@gmail.com':'lehman',
    'shawnscottcarl@gmail.com':'carl',
    'finsmaniac1551@gmail.com':'fins',
    'jakelehman100@gmail.com':'coach',
    'hankrudden@yahoo.com':'moneyman',
    'scire.ben@gmail.com':'admin',
    'williamjabbott22@gmail.com':'bittalers',
    'timjbohlman@gmail.com':'timj',
    'goodnoughdylan@gmail.com':'goody',
    'adam.schmidt520@gmail.com':'adam520',
    # New Week 4 additions (placeholder phrases - update to real passphrases as needed)
    'mzanin98@gmail.com':'zanin',
    'jlindsey3428@gmail.com':'jlindsey',
    'tomlinson6267@gmail.com':'tomlinson',
    'conor.murphy30@gmail.com':'conor'
}

# Administrators (can view all submissions)
ADMINS = {'scire.ben@gmail.com', 'jakelehman100@gmail.com'}

# Derive canonical user list from phrase map (single source of truth)
ALL_USERS = sorted(PHRASE_MAP.keys())

# Single constant for required picks (used across endpoints)
PICKS_REQUIRED = 9  # Sunday picks required count

# Monday (MNF) constants
MONDAY_REQUIRED = 4
MONDAY_FILE = DATA_DIR / 'monday_picks.json'
MONDAY_HISTORY_FILE = DATA_DIR / 'monday_history.json'
MONDAY_CSV_FILE = APP_ROOT / '09_15_Picks.csv'  # authoritative Monday picks source
def load_monday():
    if not MONDAY_FILE.exists():
        return {}
    try:
        with MONDAY_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_monday(data):
    tmp = MONDAY_FILE.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    tmp.replace(MONDAY_FILE)

def append_monday_history(email, picks):
    # History stored as an array of { email, picks, ts }
    history = []
    if MONDAY_HISTORY_FILE.exists():
        try:
            with MONDAY_HISTORY_FILE.open('r', encoding='utf-8') as f:
                history = json.load(f) or []
        except Exception:
            history = []
    entry = { 'email': email, 'picks': picks, 'ts': int(time.time()*1000) }
    history.append(entry)
    tmp = MONDAY_HISTORY_FILE.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(history, f, indent=2)
    tmp.replace(MONDAY_HISTORY_FILE)

# ================= MONDAY CSV (Authoritative) =================
def _normalize_email(raw: str) -> str:
    if not raw:
        return ''
    e = raw.strip().lower()
    # Fix known typo in CSV (double 'n')
    if e == 'hankruddenn@yahoo.com':
        return 'hankrudden@yahoo.com'
    return e

def _parse_monday_csv():
    """Parse authoritative Monday picks CSV file with fuzzy header matching.
    Accepts variable header phrasing, e.g.:
      - TB +2.5 @ HOU
      - NFL: TB +2.5 @ HOU
      - TB @ HOU O/U 42.5
      - TB / HOU Over Under - 42.5
      - LAC -3.5 @ LVR
      - LAC @ LVR O/U 46.5 (or 'Over Under - 46.5')

    Returns: { email: { picks:[spread1, total1, spread2, total2], ts } }
    Rules:
      * First row per email wins (ignore later duplicates)
      * Only registered users kept
      * Blank becomes 'NA'
      * Over/Under normalized to Over / Under
      * Team abbreviations upper-cased (TB,HOU,LAC,LVR)
    """
    results = {}
    if not MONDAY_CSV_FILE.exists():
        return results
    try:
        with MONDAY_CSV_FILE.open('r', encoding='utf-8') as f:
            # Read whole to allow manual split (handles minor header variants more easily)
            raw = f.read().strip().splitlines()
        if not raw:
            return results
        header = [h.strip() for h in raw[0].split(',')]
        lower = [h.lower() for h in header]

        def find_col(preds):
            for i,h in enumerate(lower):
                if all(p in h for p in preds):
                    return i
            return -1

        email_idx = find_col(['user']) if find_col(['user','name'])!=-1 else find_col(['email'])
        # Spread 1 (TB @ HOU) contains tb & hou and either '+'/'-' or '@'
        spread1_idx = -1
        for i,h in enumerate(lower):
            if 'tb' in h and 'hou' in h and ('@' in h or '+' in h or '-' in h) and 'o/u' not in h and 'over' not in h:
                spread1_idx = i; break
        total1_idx = -1
        for i,h in enumerate(lower):
            if 'tb' in h and 'hou' in h and ('o/u' in h or 'over' in h):
                total1_idx = i; break
        spread2_idx = -1
        for i,h in enumerate(lower):
            if 'lac' in h and ('lvr' in h or 'lv' in h) and ('@' in h or '+' in h or '-' in h) and 'o/u' not in h and 'over' not in h:
                spread2_idx = i; break
        total2_idx = -1
        for i,h in enumerate(lower):
            if 'lac' in h and ('lvr' in h or 'lv' in h) and ('o/u' in h or 'over' in h):
                total2_idx = i; break

        indices = [spread1_idx, total1_idx, spread2_idx, total2_idx]
        if email_idx < 0 or any(i < 0 for i in indices):
            print('[MONDAY][CSV][WARN] Missing required Monday columns', email_idx, indices)
        # Process rows
        for line in raw[1:]:
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(',')]
            if email_idx >= len(parts):
                continue
            email = _normalize_email(parts[email_idx])
            if not email or email in results or email not in ALL_USERS:
                continue
            picks = []
            for pi,ci in enumerate(indices):
                val = parts[ci] if ci >=0 and ci < len(parts) else ''
                val = (val or '').strip()
                if not val:
                    picks.append('NA'); continue
                if val.lower() == 'over': picks.append('Over'); continue
                if val.lower() == 'under': picks.append('Under'); continue
                # Team normalization
                up = val.upper()
                if up in ('TB','HOU','LAC','LVR','LV'):
                    if up=='LV': up='LVR'
                    picks.append(up)
                else:
                    picks.append(up)
            if len(picks)==4:
                results[email] = { 'picks': picks, 'ts': int(time.time()*1000) }
    except Exception as e:
        print(f"[MONDAY][CSV][WARN] Failed parsing CSV: {e}")
        return {}
    # Nick fallback
    nick_email = 'finsmaniac1551@gmail.com'
    if nick_email not in results and nick_email in ALL_USERS:
        results[nick_email] = { 'picks': ['NA','NA','NA','NA'], 'ts': int(time.time()*1000) }
    return results

def get_official_monday_picks():
    """Public helper to obtain authoritative Monday picks from CSV with in-memory caching window."""
    # Simple time-based cache (5s) to avoid re-reading file frequently under load.
    now = time.time()
    cache = getattr(get_official_monday_picks, '_cache', None)
    if cache and (now - cache.get('ts',0) < 5):
        return cache['data']
    data = _parse_monday_csv()
    get_official_monday_picks._cache = { 'ts': now, 'data': data }
    return data

PRESEEDED = []  # Legacy sunday seeding removed (fully migrated)

app = Flask(__name__, static_folder='.', static_url_path='')

# ---------------- Day Key Normalization Utilities -----------------
def _canon_day(day: str):
    if not day:
        return None
    d = day.strip().lower()
    if d.startswith('thu'):  # thu, thur, thurs, thursday
        return 'Thu'
    if d.startswith('fri'):
        return 'Fri'
    if d.startswith('sat'):
        return 'Sat'
    if d.startswith('sun'):
        return 'Sun'
    if d.startswith('mon'):
        return 'Mon'
    return None

def _migrate_picks_keys():
    """One-time lightweight migration: rename 'Thurs' -> 'Thu' etc in picks file.
    Idempotent; safe on every startup."""
    try:
        if not UNIFIED_PICKS_FILE.exists():
            return
        with UNIFIED_PICKS_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f) or {}
        changed = False
        # Map any plural/long forms to canonical
        for k in list(data.keys()):
            canon = _canon_day(k)
            if canon and canon != k:
                if canon not in data:  # simple rename
                    data[canon] = data[k]
                else:  # merge (keep latest ts per email)
                    for email, rec in (data[k] or {}).items():
                        existing = data[canon].get(email)
                        if not existing or existing.get('ts',0) < rec.get('ts',0):
                            data[canon][email] = rec
                del data[k]
                changed = True
        if changed:
            tmp = UNIFIED_PICKS_FILE.with_suffix('.tmp')
            with tmp.open('w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            tmp.replace(UNIFIED_PICKS_FILE)
    except Exception as e:
        print('[MIGRATE][WARN] picks key migration failed:', e)

# Flask 3 removed before_first_request; implement version-agnostic one-time init.
_INIT_DONE = False
def _run_init_once():
    global _INIT_DONE
    if _INIT_DONE:
        return
    try:
        ensure_preseed()
        _INIT_DONE = True
    except Exception as e:
        print(f"[INIT][WARN] ensure_preseed failed: {e}")

@app.before_request
def _lazy_init_hook():  # pragma: no cover
    _run_init_once()


def ensure_preseed():
    with LOCK:
        # Monday submissions are locked (CSV authoritative) -> no need to create legacy sunday json containers.
        if not MONDAY_HISTORY_FILE.exists():
            with MONDAY_HISTORY_FILE.open('w', encoding='utf-8') as f:
                json.dump([], f)
        # Initialize allowed emails file & users file baseline
        if not ALLOWED_EMAILS_FILE.exists():
            try:
                with ALLOWED_EMAILS_FILE.open('w', encoding='utf-8') as f:
                    json.dump(ALL_USERS, f, indent=2)
            except Exception:
                pass
        if not USERS_FILE.exists():
            try:
                with USERS_FILE.open('w', encoding='utf-8') as f:
                    json.dump({}, f)
            except Exception:
                pass
        # Seed users.json with hashed phrase passwords for existing roster (idempotent)
        try:
            users = _load_users()
            updated = False
            for email, phrase in PHRASE_MAP.items():
                if email not in users:
                    users[email] = {
                        'password_hash': generate_password_hash(phrase),
                        'created': int(time.time()*1000),
                        'admin': email in ADMINS,
                        'seeded': True
                    }
                    updated = True
            if updated:
                _save_users(users)
            # Perform day key migration for unified picks file (idempotent)
            _migrate_picks_keys()
        except Exception as e:
            print('[INIT][WARN] failed seeding users or migration:', e)

############################
# User Account Persistence
############################

def _load_allowed_emails():
    if ALLOWED_EMAILS_FILE.exists():
        try:
            with ALLOWED_EMAILS_FILE.open('r', encoding='utf-8') as f:
                arr = json.load(f) or []
                return { e.strip().lower() for e in arr if isinstance(e,str) and e.strip() }
        except Exception:
            return set(ALL_USERS)
    return set(ALL_USERS)

def _load_users():
    if USERS_FILE.exists():
        try:
            with USERS_FILE.open('r', encoding='utf-8') as f:
                return json.load(f) or {}
        except Exception:
            return {}
    return {}

def _save_users(data):
    tmp = USERS_FILE.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    tmp.replace(USERS_FILE)

def _sign_token(email: str) -> str:
    payload = f"{email}|{int(time.time())}"
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(payload.encode()).decode() + '.' + sig
    return token

def _verify_token(token: str):
    if not token or '.' not in token:
        return None, 'format'
    b64, sig = token.rsplit('.', 1)
    try:
        payload = base64.urlsafe_b64decode(b64.encode()).decode()
    except Exception:
        return None, 'decode'
    expected_sig = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_sig, sig):
        return None, 'sig'
    try:
        email, ts_s = payload.split('|', 1)
        ts = int(ts_s)
    except Exception:
        return None, 'payload'
    if time.time() - ts > TOKEN_TTL_SECONDS:
        return None, 'expired'
    users = _load_users()
    if email not in users:
        return None, 'unknown'
    return email, None

def _auth_from_header():
    auth = request.headers.get('Authorization','')
    if auth.lower().startswith('bearer '):
        token = auth.split(None,1)[1].strip()
        email, err = _verify_token(token)
        if err:
            return None, err
        return email, None
    return None, 'missing'


############################
# Schedule Parsing (CSV -> JSON model)
############################

def _parse_float(val):
    try:
        if val is None: return None
        s = str(val).strip()
        if s == '': return None
        return float(s)
    except Exception:
        return None

def _load_schedule_from_disk():
    """Parse schedule CSV. Supports two schemas:
    (A) Legacy multi-pick row with columns LineHome, Total, PickTypes
    (B) New one-row-per-pick with columns Market, Selection, Line, Total, Result

    Adds 'result' field to each pick definition if provided.
    If Date column missing, infers dates sequentially starting from the next (or current) real
    calendar day matching the first occurrence of each weekday in the Thu->Mon window.
    """
    if not SCHEDULE_CSV.exists():
        return { 'days': {} }
    try:
        with SCHEDULE_CSV.open('r', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        # Infer dates if missing entirely
        any_date = any((r.get('Date') or '').strip() for r in rows)
        if not any_date:
            # Build mapping of day tokens to weekday indices
            dow_map = {'THU':3,'FRI':4,'SAT':5,'SUN':6,'MON':0}
            now = datetime.now(ZoneInfo('US/Eastern')) if ZoneInfo else datetime.now()
            base = now
            assigned = {}
            # Order days in typical weekly progression
            order = ['Thu','Fri','Sat','Sun','Mon']
            for d in order:
                # Skip if not present
                if not any((r.get('Day') or '').strip() == d for r in rows):
                    continue
                target_wd = dow_map[d.upper()[:3]]
                cand = base
                for _ in range(10):  # safety bound
                    if cand.weekday() == target_wd:
                        assigned[d] = cand.strftime('%Y-%m-%d')
                        # Advance base one day for subsequent searches to avoid going backwards
                        base = cand + timedelta(days=1)
                        break
                    cand += timedelta(days=1)
            for r in rows:
                d = (r.get('Day') or '').strip()
                if d and not (r.get('Date') or '').strip() and d in assigned:
                    r['Date'] = assigned[d]
        days = {}
        for row in rows:
            day = (row.get('Day') or '').strip()
            if not day:
                continue
            sport = (row.get('Sport') or '').strip()
            event_id = (row.get('EventId') or '').strip() or None
            away = (row.get('Away') or '').strip()
            home = (row.get('Home') or '').strip()
            away_abbr = (row.get('AwayAbbr') or '').strip() or (away[:4].upper() if away else '')
            home_abbr = (row.get('HomeAbbr') or '').strip() or (home[:4].upper() if home else '')
            start_time = (row.get('StartTimeET') or '').strip()
            date_raw = (row.get('Date') or '').strip()
            prop_label = (row.get('PropLabel') or '').strip()
            result_val = (row.get('Result') or '').strip()
            market = (row.get('Market') or '').strip().upper()
            selection = (row.get('Selection') or '').strip().upper()  # optional now
            line_val = row.get('Line')
            total_val = row.get('Total')
            bucket = days.setdefault(day, { 'games': [], 'picks': [] })
            # Find or create game entry (keyed by eventId)
            game_index = None
            if event_id:
                for idx,g in enumerate(bucket['games']):
                    if g.get('eventId') == event_id:
                        game_index = idx
                        break
            if game_index is None and away and home:
                start_iso = None
                if date_raw and start_time:
                    try:
                        t_clean = start_time.replace('ET','').strip()
                        dt_date = datetime.strptime(date_raw, '%Y-%m-%d')
                        dt_time = datetime.strptime(t_clean, '%I:%M %p')
                        combined = datetime.combine(dt_date.date(), dt_time.time())
                        if ZoneInfo:
                            combined = combined.replace(tzinfo=ZoneInfo('US/Eastern'))
                        start_iso = combined.isoformat()
                    except Exception:
                        start_iso = None
                game_index = len(bucket['games'])
                bucket['games'].append({
                    'eventId': event_id,
                    'sport': sport,
                    'away': away,
                    'home': home,
                    'awayAbbr': away_abbr,
                    'homeAbbr': home_abbr,
                    'lineHome': None,
                    'total': None,
                    'start': start_time,
                    'date': date_raw,
                    'startIso': start_iso
                })
            picks_to_add = []
            if market:  # New schema single pick row
                if market == 'SPREAD' and game_index is not None:
                    # Interpret Line as the selected side's line (abs value). We'll store home-based line.
                    ln = None
                    try:
                        ln_parsed = float(line_val) if line_val not in (None,'') else None
                    except Exception:
                        ln_parsed = None
                    if ln_parsed is not None:
                        home_ab = bucket['games'][game_index]['homeAbbr']
                        away_ab = bucket['games'][game_index]['awayAbbr']
                        if selection:
                            if selection == home_ab.upper():
                                bucket['games'][game_index]['lineHome'] = ln_parsed
                            elif selection == away_ab.upper():
                                bucket['games'][game_index]['lineHome'] = -ln_parsed
                            else:
                                bucket['games'][game_index]['lineHome'] = ln_parsed
                        else:
                            bucket['games'][game_index]['lineHome'] = ln_parsed
                    spread_disp = ''
                    if bucket['games'][game_index]['lineHome'] is not None:
                        lhv = bucket['games'][game_index]['lineHome']
                        spread_disp = 'PK' if lhv == 0 else f"{lhv:+g}"
                    label = f"{away_abbr} @ {home_abbr} {spread_disp}".strip()
                    picks_to_add.append({ 'type': 'SPREAD', 'gameIndex': game_index, 'label': label, 'result': (result_val or None) })
                elif market == 'TOTAL' and game_index is not None:
                    try:
                        total_num = float(total_val) if total_val not in (None,'') else None
                    except Exception:
                        total_num = None
                    if total_num is not None:
                        bucket['games'][game_index]['total'] = total_num
                        picks_to_add.append({ 'type': 'TOTAL', 'gameIndex': game_index, 'label': f"O/U {total_num:g} ({away_abbr}/{home_abbr})", 'result': (result_val or None) })
                elif market == 'PROP':
                    picks_to_add.append({ 'type': 'PROP', 'gameIndex': game_index, 'label': prop_label or 'Prop', 'result': (result_val or None) })
            else:
                # Fallback legacy schema support (retain minimal backward compatibility)
                line_home = _parse_float(row.get('LineHome'))
                total = _parse_float(row.get('Total'))
                pick_types_raw = (row.get('PickTypes') or '').strip()
                pick_types = [p.strip().upper() for p in pick_types_raw.split(',') if p.strip()]
                if line_home is not None and game_index is not None:
                    bucket['games'][game_index]['lineHome'] = line_home
                if total is not None and game_index is not None:
                    bucket['games'][game_index]['total'] = total
                for pt in pick_types:
                    if pt == 'SPREAD' and game_index is not None:
                        ln = bucket['games'][game_index]['lineHome']
                        spread_str = '' if ln is None else ('PK' if ln == 0 else f"{ln:+g}")
                        label = f"{away_abbr} @ {home_abbr} {spread_str}".strip()
                        picks_to_add.append({ 'type': 'SPREAD', 'gameIndex': game_index, 'label': label, 'result': result_val or None })
                    elif pt == 'TOTAL' and game_index is not None and bucket['games'][game_index].get('total') is not None:
                        tv = bucket['games'][game_index]['total']
                        picks_to_add.append({ 'type': 'TOTAL', 'gameIndex': game_index, 'label': f"O/U {tv:g} ({away_abbr}/{home_abbr})", 'result': result_val or None })
                    elif pt == 'PROP':
                        picks_to_add.append({ 'type': 'PROP', 'gameIndex': game_index, 'label': prop_label or 'Prop', 'result': result_val or None })
            for pe in picks_to_add:
                bucket['picks'].append(pe)
        return { 'days': days }
    except Exception as e:
        print('[SCHEDULE][ERROR] Failed parsing schedule CSV:', e)
        return { 'days': {} }

def _load_schedule():
    # Simple memory cache; reload version increments
    with SCHEDULE_LOCK:
        if _SCHEDULE_CACHE['data'] is None:
            data = _load_schedule_from_disk()
            _SCHEDULE_CACHE['data'] = data
            _SCHEDULE_CACHE['version'] += 1
            _SCHEDULE_CACHE['ts'] = time.time()
            # Persist JSON snapshot for debugging
            try:
                with SCHEDULE_JSON.open('w', encoding='utf-8') as f:
                    json.dump({ 'version': _SCHEDULE_CACHE['version'], **data }, f, indent=2)
            except Exception:
                pass
        return _SCHEDULE_CACHE['data'], _SCHEDULE_CACHE['version']

def _force_reload_schedule():
    with SCHEDULE_LOCK:
        data = _load_schedule_from_disk()
        _SCHEDULE_CACHE['data'] = data
        _SCHEDULE_CACHE['version'] += 1
        _SCHEDULE_CACHE['ts'] = time.time()
        try:
            with SCHEDULE_JSON.open('w', encoding='utf-8') as f:
                json.dump({ 'version': _SCHEDULE_CACHE['version'], **data }, f, indent=2)
        except Exception:
            pass
        return data, _SCHEDULE_CACHE['version']

############################
# Unified Picks Persistence
############################

def load_unified_picks():
    # Fallback: if data/picks.json missing but a legacy root-level picks.json exists (from earlier deploys),
    # copy it into place one time so scoring can proceed without manual intervention on Render.
    if not UNIFIED_PICKS_FILE.exists():
        legacy_root = APP_ROOT / 'picks.json'
        if legacy_root.exists():
            try:
                with legacy_root.open('r', encoding='utf-8') as f:
                    data = json.load(f) or {}
                # Write into data/picks.json for future loads
                save_unified_picks(data)
                return data
            except Exception as e:
                print('[PICKS][WARN] Failed migrating root picks.json -> data/picks.json:', e)
        return {}
    try:
        with UNIFIED_PICKS_FILE.open('r', encoding='utf-8') as f:
            data = json.load(f) or {}
        # Merge legacy root picks.json if it has days missing from current unified file (e.g. Thu not copied earlier)
        try:
            legacy_root = APP_ROOT / 'picks.json'
            if legacy_root.exists():
                with legacy_root.open('r', encoding='utf-8') as lf:
                    legacy = json.load(lf) or {}
                changed = False
                for day, day_map in (legacy or {}).items():
                    if day not in data or not data.get(day):
                        if isinstance(day_map, dict):
                            data[day] = day_map
                            changed = True
                if changed:
                    # Write back merged data (avoid calling save_unified_picks earlier to prevent recursion risk)
                    tmp = UNIFIED_PICKS_FILE.with_suffix('.tmp')
                    with tmp.open('w', encoding='utf-8') as wf:
                        json.dump(data, wf, indent=2)
                    tmp.replace(UNIFIED_PICKS_FILE)
                    print('[PICKS][INFO] Merged missing day(s) from legacy root picks.json into data/picks.json')
        except Exception as e:
            print('[PICKS][WARN] Failed merging legacy root picks.json:', e)
        # Aggressive normalization pass: canonical day key, drop empty entries, uppercase picks
        try:
            norm_changed = False
            # Canonicalize Thu key variants
            for alt in list(data.keys()):
                canon = _canon_day(alt)
                if canon and canon != alt:
                    if canon not in data:
                        data[canon] = data[alt]
                    else:
                        # merge entries (keep latest ts)
                        for email, rec in (data[alt] or {}).items():
                            existing = data[canon].get(email)
                            if not existing or existing.get('ts',0) < (rec or {}).get('ts',0):
                                data[canon][email] = rec
                    del data[alt]
                    norm_changed = True
            # Normalize each day
            for day, dmap in list(data.items()):
                if not isinstance(dmap, dict):
                    continue
                to_delete = []
                for email, rec in dmap.items():
                    if not isinstance(rec, dict):
                        to_delete.append(email); continue
                    picks_arr = rec.get('picks')
                    if not isinstance(picks_arr, list):
                        to_delete.append(email); continue
                    # Uppercase & trim
                    up = [ (str(v).strip().upper() if v is not None else '') for v in picks_arr ]
                    # For Thu enforce length 3 (truncate or pad empties)
                    if day == 'Thu':
                        if len(up) > 3:
                            up = up[:3]
                        elif len(up) < 3:
                            up = up + ['' for _ in range(3-len(up))]
                    # Remove if all empty
                    if not any(s for s in up):
                        to_delete.append(email); continue
                    if up != picks_arr:
                        rec['picks'] = up
                        norm_changed = True
                for email in to_delete:
                    del dmap[email]; norm_changed = True
            if norm_changed:
                tmp = UNIFIED_PICKS_FILE.with_suffix('.tmp')
                with tmp.open('w', encoding='utf-8') as wf:
                    json.dump(data, wf, indent=2)
                tmp.replace(UNIFIED_PICKS_FILE)
                print('[PICKS][INFO] Normalized unified picks store (canonical day keys, cleaned entries)')
        except Exception as e:
            print('[PICKS][WARN] Normalization pass failed:', e)
        return data
    except Exception:
        return {}

def save_unified_picks(data):
    tmp = UNIFIED_PICKS_FILE.with_suffix('.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    tmp.replace(UNIFIED_PICKS_FILE)

@app.route('/api/schedule')
def api_schedule():
    sched, ver = _load_schedule()
    return jsonify({ 'ok': True, 'version': ver, 'days': sched.get('days', {}) })

@app.route('/api/schedule/reload', methods=['POST'])
def api_schedule_reload():
    payload = request.get_json(force=True, silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    phrase = (payload.get('phrase') or '').strip()
    if email not in ADMINS:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    expected = PHRASE_MAP.get(email)
    if not expected or expected.lower() != phrase.lower():
        return jsonify({ 'ok': False, 'error': 'invalid_phrase' }), 403
    data, ver = _force_reload_schedule()
    return jsonify({ 'ok': True, 'version': ver, 'days': data.get('days', {}) })

############################
# Unified Picks Endpoints (/api/picks/*)
############################

def _check_phrase(email, phrase):
    expected = PHRASE_MAP.get(email)
    return expected and expected.lower() == phrase.lower()

## Legacy sunday unlock/submit endpoints removed (fully migrated)

@app.route('/api/picks/public')
def picks_public_unified():
    raw_day = (request.args.get('day') or '').strip()
    day = _canon_day(raw_day)
    if not day:
        return jsonify({ 'ok': False, 'error': 'missing_day' }), 400
    sched, _ = _load_schedule()
    schedule_days = list((sched.get('days') or {}).keys())
    if day not in (sched.get('days') or {}):
        # Relax: allow access even if schedule missing (e.g., minimal week setup). Log once.
        print(f"[PICKS][INFO] Requested day '{day}' not in schedule days {schedule_days}; proceeding with unified picks store only.")
    all_p = load_unified_picks()
    day_map = all_p.get(day) or {}
    # Return only users who fully submitted (every slot non-empty OR allow empties? treat length rule only)
    filtered = { u: rec for u, rec in day_map.items() if isinstance(rec.get('picks'), list) }
    return jsonify({ 'ok': True, 'entries': filtered })

@app.route('/api/picks/status/<day>')
def picks_status_day(day):
    day = _canon_day(day)
    sched, _ = _load_schedule()
    schedule_days = list((sched.get('days') or {}).keys())
    if day not in (sched.get('days') or {}):
        print(f"[PICKS][INFO] Status request for day '{day}' not in schedule days {schedule_days}; returning picks file status only.")
    picks_map = load_unified_picks()
    day_map = picks_map.get(day) or {}
    return jsonify({ 'ok': True, 'submitted': list(day_map.keys()), 'count': len(day_map) })

## Sunday phrase-based endpoints fully removed.

# ================= MONDAY (MNF) ENDPOINTS =================
# Auth model: reuse phrase map; overwrite allowed (latest wins) for flexibility.

@app.route('/auth/login', methods=['POST'])
def auth_login():
    payload = request.get_json(force=True, silent=True) or {}
    email = payload.get('userEmail','').strip().lower()
    password = payload.get('pass','').strip()
    if email not in ALL_USERS:
        return jsonify({ 'error':'user_not_found' }), 404
    expected = PHRASE_MAP.get(email)
    if not expected or expected.lower() != password.lower():
        return jsonify({ 'error':'invalid_pass' }), 401
    return jsonify({ 'ok': True, 'isAdmin': email in ADMINS })

@app.route('/picks/monday/user', methods=['POST'])
def monday_user():
    payload = request.get_json(force=True, silent=True) or {}
    email = payload.get('userEmail','').strip().lower()
    password = payload.get('pass','').strip()
    if email not in ALL_USERS:
        return jsonify({ 'error':'user_not_found' }), 404
    expected = PHRASE_MAP.get(email)
    if not expected or expected.lower() != password.lower():
        return jsonify({ 'error':'invalid_pass' }), 401
    data = load_monday()
    rec = data.get(email)
    return jsonify(rec or None)

@app.route('/picks/monday/status')
def monday_status():
    data = load_monday()
    return jsonify({ 'submitted': list(data.keys()) })

@app.route('/picks/monday/public')
def monday_public():
    data = load_monday()
    # Public Monday picks: show admins' picks only.
    filtered = { k: data[k] for k in ADMINS if k in data }
    return jsonify(filtered)

@app.route('/picks/monday/history')
def monday_history():
    """Return full Monday submission history (all overwrites) restricted to Ben's phrase auth.
    Query params: userEmail, pass (kept simple to allow GET without body)."""
    email = request.args.get('userEmail','').strip().lower()
    password = request.args.get('pass','').strip()
    if email != 'scire.ben@gmail.com':
        return jsonify({'error':'forbidden'}), 403
    expected = PHRASE_MAP.get(email)
    if not expected or expected.lower() != password.lower():
        return jsonify({'error':'invalid_pass'}), 401
    # Load history list
    try:
        if MONDAY_HISTORY_FILE.exists():
            with MONDAY_HISTORY_FILE.open('r', encoding='utf-8') as f:
                hist = json.load(f) or []
        else:
            hist = []
    except Exception:
        hist = []
    return jsonify(hist)

@app.route('/picks/monday', methods=['POST'])
def monday_submit_locked():
    """Submission endpoint now locked; picks are sourced exclusively from CSV.
    Always returns 403 to indicate no further edits allowed."""
    return jsonify({ 'error':'locked', 'message':'Monday picks are locked – CSV authoritative.' }), 403

@app.route('/picks/monday/all', methods=['POST'])
def monday_all_deprecated():
    """Deprecated: returns 410 Gone to discourage reliance on JSON store."""
    return jsonify({ 'error':'gone', 'message':'Endpoint deprecated. Use /picks/monday/official for authoritative picks.' }), 410

@app.route('/picks/monday/official')
def monday_official():
    """Return authoritative Monday picks from CSV (ignores runtime submissions).
    Response format: { ok:true, entries: { email: { picks:[...4], ts } } }
    No auth required (only reveals picks already locked in)."""
    official = get_official_monday_picks()
    return jsonify({ 'ok': True, 'entries': official })

############################
# New Auth & Editable Picks (pre-kickoff) System
############################

def _pick_lock_matrix(day: str):
    """Return list[bool] locked flags for each pick index for the given day.
    Locked if current time >= game start (parsed ISO) for picks tied to a game.
    Props without a start remain unlocked unless we decide to tie them later.
    """
    sched, _ = _load_schedule()
    day_def = (sched.get('days') or {}).get(day) or {}
    pick_defs = day_def.get('picks') or []
    games = day_def.get('games') or []
    now = datetime.now(ZoneInfo('US/Eastern')) if ZoneInfo else datetime.now()
    locks = []
    for pd in pick_defs:
        gi = pd.get('gameIndex')
        locked = False
        if gi is not None and 0 <= gi < len(games):
            start_iso = games[gi].get('startIso')
            if start_iso:
                try:
                    dt = datetime.fromisoformat(start_iso)
                    # If dt naive & ZoneInfo available, treat as Eastern naive
                    if dt.tzinfo is None and ZoneInfo:
                        dt = dt.replace(tzinfo=ZoneInfo('US/Eastern'))
                    if now >= dt:
                        locked = True
                except Exception:
                    locked = False
        locks.append(locked)
    return locks

@app.route('/api/auth/create', methods=['POST'])
def auth_create():
    payload = request.get_json(force=True, silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    password = (payload.get('password') or '').strip()
    if not email or not password:
        return jsonify({ 'ok': False, 'error': 'missing_fields' }), 400
    allowed = _load_allowed_emails()
    if email not in allowed:
        return jsonify({ 'ok': False, 'error': 'not_allowed' }), 403
    users = _load_users()
    existing = users.get(email)
    # Allow overwriting a seeded account exactly once (has 'seeded': True and no 'claimed')
    if existing and not existing.get('seeded'):
        return jsonify({ 'ok': False, 'error': 'exists' }), 409
    if len(password) < 3:  # relaxed per simplified security requirement
        return jsonify({ 'ok': False, 'error': 'weak_password' }), 400
    users[email] = {
        'password_hash': generate_password_hash(password),
        'created': existing.get('created') if existing else int(time.time()*1000),
        'admin': email in ADMINS,
        'claimed': int(time.time()*1000)
    }
    _save_users(users)
    token = _sign_token(email)
    return jsonify({ 'ok': True, 'token': token, 'isAdmin': email in ADMINS, 'claimed': True })

@app.route('/api/auth/login', methods=['POST'])
def auth_login_new():
    payload = request.get_json(force=True, silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    password = (payload.get('password') or '').strip()
    if not email or not password:
        return jsonify({ 'ok': False, 'error': 'missing_fields' }), 400
    users = _load_users()
    rec = users.get(email)
    if not rec:
        return jsonify({ 'ok': False, 'error': 'not_found' }), 404
    if not check_password_hash(rec.get('password_hash',''), password):
        return jsonify({ 'ok': False, 'error': 'invalid_credentials' }), 401
    token = _sign_token(email)
    return jsonify({ 'ok': True, 'token': token, 'isAdmin': bool(rec.get('admin')) })

@app.route('/api/auth/status')
def auth_status():
    email, err = _auth_from_header()
    if err:
        return jsonify({ 'ok': False, 'error': err }), 401
    users = _load_users()
    rec = users.get(email) or {}
    return jsonify({ 'ok': True, 'email': email, 'isAdmin': bool(rec.get('admin')), 'claimed': 'claimed' in rec or not rec.get('seeded') })

@app.route('/api/schedule/countdowns')
def schedule_countdowns():
    """Return per-day pick indices -> ms until lock (0 if locked) for active schedule.
    Useful for lightweight polling on frontend (every 60s)."""
    sched, _ = _load_schedule()
    days = sched.get('days') or {}
    now = datetime.now(ZoneInfo('US/Eastern')) if ZoneInfo else datetime.now()
    resp = {}
    for day, defn in days.items():
        games = defn.get('games') or []
        picks = defn.get('picks') or []
        arr = []
        for pd in picks:
            gi = pd.get('gameIndex')
            ms = None
            if gi is not None and 0 <= gi < len(games):
                start_iso = games[gi].get('startIso')
                if start_iso:
                    try:
                        dt = datetime.fromisoformat(start_iso)
                        if dt.tzinfo is None and ZoneInfo:
                            dt = dt.replace(tzinfo=ZoneInfo('US/Eastern'))
                        diff = (dt - now).total_seconds()
                        ms = int(diff * 1000)
                        if ms < 0: ms = 0
                    except Exception:
                        ms = None
            arr.append(ms)
        resp[day] = arr
    return jsonify({ 'ok': True, 'countdowns': resp, 'now': int(time.time()*1000) })

@app.route('/api/picks/get')
def picks_get():
    day = (request.args.get('day') or '').strip()
    if not day:
        return jsonify({ 'ok': False, 'error': 'missing_day' }), 400
    email, err = _auth_from_header()
    if err:
        return jsonify({ 'ok': False, 'error': f'auth_{err}' }), 401
    sched, _ = _load_schedule()
    day_def = (sched.get('days') or {}).get(day)
    if not day_def:
        return jsonify({ 'ok': False, 'error': 'unknown_day' }), 404
    picks_map = load_unified_picks()
    day_map = picks_map.get(day) or {}
    rec = day_map.get(email)
    pick_defs = day_def.get('picks') or []
    locks = _pick_lock_matrix(day)
    # Guarantee array length
    picks_arr = rec.get('picks') if rec else ['' for _ in pick_defs]
    return jsonify({ 'ok': True, 'picks': picks_arr, 'locked': locks, 'now': int(time.time()*1000) })

@app.route('/api/picks/save', methods=['POST'])
def picks_save():
    payload = request.get_json(force=True, silent=True) or {}
    day = (payload.get('day') or '').strip()
    new_picks = payload.get('picks')
    if not isinstance(new_picks, list):
        return jsonify({ 'ok': False, 'error': 'bad_picks' }), 400
    email, err = _auth_from_header()
    if err:
        return jsonify({ 'ok': False, 'error': f'auth_{err}' }), 401
    sched, _ = _load_schedule()
    day_def = (sched.get('days') or {}).get(day)
    if not day_def:
        return jsonify({ 'ok': False, 'error': 'unknown_day' }), 404
    pick_defs = day_def.get('picks') or []
    if len(new_picks) != len(pick_defs):
        return jsonify({ 'ok': False, 'error': 'wrong_length', 'expected': len(pick_defs) }), 400
    locks = _pick_lock_matrix(day)
    with LOCK:
        all_p = load_unified_picks()
        day_map = all_p.setdefault(day, {})
        rec = day_map.get(email) or { 'picks': ['' for _ in pick_defs], 'ts': int(time.time()*1000) }
        existing = rec['picks']
        attempted_locked = []
        for i,(new_val,locked) in enumerate(zip(new_picks, locks)):
            if locked and existing[i] and new_val != existing[i]:
                attempted_locked.append(i)
        if attempted_locked:
            return jsonify({ 'ok': False, 'error': 'locked_picks', 'indices': attempted_locked }), 409
        # Apply only non-locked (or empty locked that user hasn't picked previously -> keep existing)
        changed = False
        for i,(new_val,locked) in enumerate(zip(new_picks, locks)):
            if locked:
                continue
            if new_val != existing[i]:
                existing[i] = (new_val or '').strip().upper()
                changed = True
        if changed:
            rec['ts'] = int(time.time()*1000)
        day_map[email] = rec
        save_unified_picks(all_p)
    return jsonify({ 'ok': True, 'saved': True, 'locked': locks })

@app.route('/api/picks/submit_day', methods=['POST'])
def picks_submit_day():
    """Lightweight day submission endpoint for quick form (email-only trust model).
    Body: { day:'Thurs', email, picks:[...] }
    - Email must be in ALL_USERS
    - For 'Thurs' currently expect exactly 3 picks: [SPREAD, TOTAL, PROP]
    - Values normalized upper-case; minimal validation of choices.
    - Overwrites allowed (no lock) until we integrate kickoff locking via schedule.
    """
    payload = request.get_json(force=True, silent=True) or {}
    day = _canon_day(payload.get('day'))
    email = (payload.get('email') or '').strip().lower()
    picks = payload.get('picks')
    if day not in ('Thu','Fri','Sat','Sun','Mon'):
        return jsonify({ 'ok': False, 'error': 'bad_day' }), 400
    # Allow ANY email now (open participation). If you want to restrict later, re-enable whitelist check.
    if not email or '@' not in email:
        return jsonify({ 'ok': False, 'error': 'invalid_email' }), 400
    if not isinstance(picks, list):
        return jsonify({ 'ok': False, 'error': 'bad_picks' }), 400
    # Simple shape validation for Thursday (3 picks). Other days can expand later.
    if day == 'Thu' and len(picks) != 3:
        return jsonify({ 'ok': False, 'error': 'wrong_length', 'expected': 3 }), 400
    norm = []
    for i,v in enumerate(picks):
        if v is None: v = ''
        s = str(v).strip().upper()
        if day == 'Thu':
            if i == 0 and s not in ('PHI','NYG'):
                return jsonify({ 'ok': False, 'error': 'invalid_spread' }), 400
            if i == 1 and s not in ('OVER','UNDER'):
                return jsonify({ 'ok': False, 'error': 'invalid_total' }), 400
            if i == 2 and s not in ('YES','NO'):
                return jsonify({ 'ok': False, 'error': 'invalid_prop' }), 400
        norm.append(s)
    with LOCK:
        all_p = load_unified_picks()
        day_map = all_p.setdefault(day, {})
        rec = day_map.get(email) or { 'picks': ['' for _ in norm], 'ts': int(time.time()*1000) }
        rec['picks'] = norm
        rec['ts'] = int(time.time()*1000)
        day_map[email] = rec
        save_unified_picks(all_p)
    return jsonify({ 'ok': True, 'email': email, 'day': day, 'picks': norm, 'ts': rec['ts'] })


############################
# Live Scoring / Leaderboard Endpoint
############################

def _normalize_pick_value(raw: str):
    if raw is None:
        return ''
    s = str(raw).strip().upper()
    # Allow shorthand for totals/props (O/U, Y/N)
    if s in ('O','OVER'): return 'OVER'
    if s in ('U','UNDER'): return 'UNDER'
    if s in ('Y','YES'): return 'YES'
    if s in ('N','NO'): return 'NO'
    return s

def _compute_current_scores():
    """Compute per-user tally of correct picks with per-day breakdown.
    Returns structure:
      {
        totalPossible: int,
        dayOrder: [day,...],
        entries: [ { email, score, answered, perDay: { day: { score, answered } } } ]
      }
    """
    sched, _ = _load_schedule()
    all_picks = load_unified_picks()
    days = sched.get('days') or {}
    # --- Thursday auto-finalization override (NYG / Over / YES) ---
    try:
        thu = days.get('Thu') or days.get('Thurs')
        if thu:
            changed = False
            for p in (thu.get('picks') or []):
                t = (p.get('type') or '').upper()
                if p.get('result'):  # already graded
                    continue
                if t=='SPREAD':
                    p['result'] = 'NYG'; changed = True
                elif t=='TOTAL':
                    p['result'] = 'OVER'; changed = True
                elif t=='PROP':
                    p['result'] = 'YES'; changed = True
            if changed:
                try:
                    with (DATA_DIR / 'schedule_autofinal_debug.json').open('w', encoding='utf-8') as f:
                        json.dump(sched, f, indent=2)
                except Exception:
                    pass
    except Exception as e:
        print('[AUTO-FINAL][WARN] Thursday override failed:', e)
    # Preserve a stable deterministic day order based on schedule 'order' then name
    ordered_days = sorted(days.keys(), key=lambda d: (days[d].get('order', 0), d))
    per_user = {}
    for day in ordered_days:
        defn = days[day]
        pick_defs = defn.get('picks') or []
        day_user_map = all_picks.get(day) or {}
        for email, rec in day_user_map.items():
            upicks = rec.get('picks') or []
            entry = per_user.setdefault(email, { 'score':0, 'answered':0, 'perDay':{} })
            dstat = entry['perDay'].setdefault(day, { 'score':0, 'answered':0 })
            for idx, pd in enumerate(pick_defs):
                if idx >= len(upicks):
                    continue
                result_val = _normalize_pick_value(pd.get('result') or '')
                if not result_val or result_val == 'PUSH':
                    continue
                user_raw = _normalize_pick_value(upicks[idx])
                if not user_raw:
                    continue
                dstat['answered'] += 1
                entry['answered'] += 1
                if user_raw == result_val:
                    dstat['score'] += 1
                    entry['score'] += 1
    total_picks = sum(len((defn or {}).get('picks') or []) for defn in days.values())
    # Include every known user (ALL_USERS) even if they have 0 submissions so far
    leaderboard = []
    all_emails = set(ALL_USERS) | set(per_user.keys())
    for email in sorted(all_emails):
        rec = per_user.get(email, { 'score':0, 'answered':0, 'perDay':{} })
        leaderboard.append({
            'email': email,
            'score': rec['score'],
            'answered': rec['answered'],
            'totalPossible': total_picks,
            'perDay': rec['perDay']
        })
    leaderboard.sort(key=lambda r: (-r['score'], r['answered'], r['email']))
    return { 'totalPossible': total_picks, 'entries': leaderboard, 'dayOrder': ordered_days }

@app.route('/api/leaderboard')
def api_leaderboard():
    data = _compute_current_scores()
    return jsonify({ 'ok': True, **data, 'generated': int(time.time()*1000) })


############################
# Admin submissions monitoring
############################

def _require_admin():
    """Validate admin via standard bearer token auth.

    Previous implementation attempted to parse the raw bearer token assuming a
    'email:...' structure which does not match the signed token format
    (base64(email|ts).hmacsig). We now simply reuse _auth_from_header and then
    check the stored user admin flag for correctness.
    Returns the admin email on success, else None.
    """
    email, err = _auth_from_header()
    if err:
        return None
    users = _load_users()
    rec = users.get(email) or {}
    if not rec.get('admin') and email not in ADMINS:
        return None
    return email

@app.route('/api/admin/submissions')
def api_admin_submissions():
    if not _require_admin():
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    sched, _ = _load_schedule()
    picks = load_unified_picks()
    out = {}
    for day, dmap in (picks or {}).items():
        day_list = []
        for email, rec in (dmap or {}).items():
            day_list.append({ 'email': email, 'count': len(rec.get('picks') or []), 'ts': rec.get('ts') })
        out[day] = day_list
    return jsonify({ 'ok': True, 'days': out, 'dayDefinitions': list((sched.get('days') or {}).keys()) })

@app.route('/api/admin/day_picks')
def api_admin_day_picks():
    """Return full raw picks for a given day (all users) including lock flags & results.
    Query: day=<DayName>
    Only for admins. This directly surfaces users' selections for auditing.
    """
    admin_email = _require_admin()
    if not admin_email:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    day = (request.args.get('day') or '').strip()
    if not day:
        return jsonify({ 'ok': False, 'error': 'missing_day' }), 400
    sched, _ = _load_schedule()
    day_def = (sched.get('days') or {}).get(day)
    if not day_def:
        return jsonify({ 'ok': False, 'error': 'unknown_day' }), 404
    pick_defs = day_def.get('picks') or []
    locks = _pick_lock_matrix(day)
    all_p = load_unified_picks()
    day_map = all_p.get(day) or {}
    # Build normalized structure: { email: { picks:[...], ts } }
    out = {}
    for email, rec in day_map.items():
        out[email] = { 'picks': rec.get('picks') or [], 'ts': rec.get('ts') }
    return jsonify({
        'ok': True,
        'admin': admin_email,
        'day': day,
        'definitions': [ { 'label': pd.get('label'), 'type': pd.get('type'), 'result': pd.get('result') } for pd in pick_defs ],
        'locks': locks,
        'entries': out,
        'count': len(out)
    })

@app.route('/api/admin/all_picks')
def api_admin_all_picks():
    """Return all picks for all days for admins (raw). Useful for snapshotting.
    Returns { ok, days: { Day: { email: { picks, ts } } }, scheduleVersion }
    """
    admin_email = _require_admin()
    if not admin_email:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    sched, ver = _load_schedule()
    all_p = load_unified_picks()
    # Shallow copy to avoid accidental mutation downstream
    safe = {}
    for day, dmap in (all_p or {}).items():
        safe[day] = { email: { 'picks': rec.get('picks') or [], 'ts': rec.get('ts') } for email, rec in (dmap or {}).items() }
    return jsonify({ 'ok': True, 'admin': admin_email, 'scheduleVersion': ver, 'days': safe })


@app.route('/healthz')
def healthz():
    """Lightweight health/diagnostic endpoint.
    Returns service + data file status (no auth). Safe metadata only.
    """
    try:
        monday = load_monday()
        unified = load_unified_picks()
        now_ms = int(time.time()*1000)
        def file_meta(path: Path):
            if path.exists():
                try:
                    stat = path.stat()
                    return {
                        'exists': True,
                        'size': stat.st_size,
                        'mtime': int(stat.st_mtime * 1000)
                    }
                except Exception:
                    return { 'exists': True, 'error': 'stat_failed' }
            return { 'exists': False }
        unified_counts = { day: len(v or {}) for day,v in unified.items() }
        resp = {
            'ok': True,
            'time': now_ms,
            'usersTotal': len(ALL_USERS),
            'unifiedDays': unified_counts,
            'monday': {
                'submittedCount': len(monday),
                'records': len(monday),
                'required': MONDAY_REQUIRED
            },
            'files': {
                'unifiedPicks': file_meta(UNIFIED_PICKS_FILE),
                'mondayPicks': file_meta(MONDAY_FILE),
                'mondayHistory': file_meta(MONDAY_HISTORY_FILE),
                'schedule': file_meta(SCHEDULE_CSV)
            }
        }
        return jsonify(resp), 200
    except Exception as e:
        return jsonify({ 'ok': False, 'error': 'health_failed', 'detail': str(e) }), 500


@app.route('/')
def root():
    return send_from_directory('.', 'leaderboard.html')

# Explicit static routes for key frontend pages & basic health check
@app.route('/leaderboard.html')
def leaderboard_page():
    return send_from_directory(APP_ROOT, 'leaderboard.html')

@app.route('/picks.html')
def picks_page():
    return send_from_directory(APP_ROOT, 'picks.html')


if __name__ == '__main__':
    ensure_preseed()
    port = int(os.environ.get('PORT', '8000'))
    app.run(host='0.0.0.0', port=port)
