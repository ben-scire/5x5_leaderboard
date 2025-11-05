from flask import Blueprint, jsonify, request, current_app
import json, os, time, csv, datetime
import pathlib

picks_bp = Blueprint('picks', __name__)

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / 'data'

MONDAY_LABELS = [
    'NFL: BUF -3.5 @ ATL (Spread)',
    'NFL: BUF -3.5 @ ATL (Total O/U 49.5)',
    'NFL: BUF -3.5 @ ATL (Prop: Bijan Robinson AND James Cook 60+ rushing yards EACH)',
    'NFL: CHI +5.5 @ WSH (Spread)',
    'NFL: CHI +5.5 @ WSH (Total O/U 48.5)',
    'NFL: CHI +5.5 @ WSH (Prop: Jayden Daniels OR Caleb Williams Anytime rush/rec TD)'
]

MONDAY_SCHEDULE = [
    {
        'sport': 'NFL',
        'eventId': None,
        'away': 'Buffalo Bills',
        'awayAbbr': 'BUF',
        'home': 'Atlanta Falcons',
        'homeAbbr': 'ATL',
        'lineHome': +3.5,
        'total': 49.5,
        'start': '2025-10-13T23:30:00Z'
    },
    {
        'sport': 'NFL',
        'eventId': None,
        'away': 'Chicago Bears',
        'awayAbbr': 'CHI',
        'home': 'Washington Commanders',
        'homeAbbr': 'WSH',
        'lineHome': -5.5,
        'total': 48.5,
        'start': '2025-10-14T01:50:00Z'
    }
]

MONDAY_FILE = DATA_DIR / 'picks' / 'monday_picks.json'
MONDAY_LOCK_FILE = DATA_DIR / 'picks' / 'monday_locked.json'
MONDAY_PREFILL_DEFAULT = {
    "kylejkz11@gmail.com": ["BUF", "UNDER", "YES", "CHI", "OVER", "YES"],
    "max1solov@gmail.com": ["BUF", "OVER", "YES", "WSH", "OVER", "NO"],
    "samuel.lehman3337@gmail.com": ["BUF", "OVER", "YES", "CHI", "UNDER", "NO"],
    "shawnscottcarl@gmail.com": ["ATL", "UNDER", "YES", "WSH", "OVER", "NO"],
    "finsmaniac1551@gmail.com": ["BUF", "OVER", "NO", "WSH", "UNDER", "NO"],
    "jakelehman100@gmail.com": ["BUF", "UNDER", "YES", "CHI", "UNDER", "NO"],
    "hankrudden@yahoo.com": ["ATL", "UNDER", "YES", "WSH", "UNDER", "NO"],
    "scire.ben@gmail.com": ["BUF", "UNDER", "YES", "WSH", "UNDER", "NO"],
    "williamjabbott22@gmail.com": ["BUF", "UNDER", "YES", "CHI", "UNDER", "NO"],
    "timjbohlman@gmail.com": ["BUF", "UNDER", "YES", "CHI", "UNDER", "NO"],
    "goodnoughdylan@gmail.com": ["BUF", "UNDER", "YES", "CHI", "UNDER", "NO"],
    "jaked9577@yahoo.com": ["BUF", "OVER", "YES", "WSH", "OVER", "NO"],
    "sam.scire@gmail.com": ["BUF", "OVER", "NO", "WSH", "UNDER", "NO"],
    "sam.scire@hotmail.com": ["BUF", "UNDER", "YES", "WSH", "UNDER", "NO"],
    "soligonaustin@outlook.com": ["ATL", "UNDER", "WSH", "CHI", "UNDER", "NO"],
    "amacdonald171@gmail.com": ["BUF", "OVER", "YES", "WSH", "UNDER", "NO"],
    "jlindsey3428@gmail.com": ["BUF", "OVER", "YES", "CHI", "UNDER", "NO"],
    "wyaggy3@gmail.com": ["ATL", "UNDER", "YES", "WSH", "UNDER", "NO"]
}


def _normalize_monday_entry(picks):
    if not isinstance(picks, list):
        picks = []
    cleaned = [str(p or '').strip().upper() for p in picks[:len(MONDAY_LABELS)]]
    if len(cleaned) < len(MONDAY_LABELS):
        cleaned.extend([''] * (len(MONDAY_LABELS) - len(cleaned)))
    return cleaned


def _ensure_monday_file():
    try:
        if not MONDAY_FILE.exists():
            MONDAY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with MONDAY_FILE.open('w', encoding='utf-8') as f:
                json.dump(MONDAY_PREFILL_DEFAULT, f, indent=2)
            return True
    except Exception:
        pass
    return False


def _load_monday():
    if MONDAY_FILE.exists():
        try:
            with MONDAY_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                out = {}
                for email, picks in data.items():
                    if not isinstance(email, str):
                        continue
                    out[email.strip().lower()] = _normalize_monday_entry(picks)
                if out:
                    return out
        except Exception:
            pass
    return { email: _normalize_monday_entry(picks) for email, picks in MONDAY_PREFILL_DEFAULT.items() }


def _save_monday(data: dict):
    try:
        MONDAY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with MONDAY_FILE.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


_ensure_monday_file()
MONDAY_PICKS = _load_monday()
try:
    _MONDAY_MTIME = MONDAY_FILE.stat().st_mtime if MONDAY_FILE.exists() else None
except Exception:
    _MONDAY_MTIME = None


def _refresh_monday(force: bool = False):
    global MONDAY_PICKS, _MONDAY_MTIME
    try:
        mtime = MONDAY_FILE.stat().st_mtime if MONDAY_FILE.exists() else None
    except Exception:
        mtime = None
    if not force and mtime == _MONDAY_MTIME:
        return False
    MONDAY_PICKS = _load_monday()
    _MONDAY_MTIME = mtime
    return True


@picks_bp.route('/api/picks/monday/labels')
def monday_labels():
    return jsonify({ 'ok': True, 'labels': MONDAY_LABELS })

# Admin routes
@picks_bp.route('/api/admin/sunday/override_user', methods=['POST'])
def admin_sunday_override_user():
    """Admin: Hard override a single user's Sunday picks (partial or full).
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
    if len(adj) > len(SUNDAY_LABELS):
        adj = adj[:len(SUNDAY_LABELS)]
    if len(adj) < len(SUNDAY_LABELS):
        adj += ['']*(len(SUNDAY_LABELS)-len(adj))
    # Before snapshot
    before = SUNDAY_PICKS.get(email, ['']*len(SUNDAY_LABELS))[:]
    SUNDAY_PICKS[email] = adj
    if not _save_sunday(SUNDAY_PICKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    _refresh_all_users()
    return jsonify({ 'ok': True, 'email': email, 'before': before, 'after': adj })

RESULTS = ['NYG', 'OVER', 'NO']
FRIDAY_RESULTS = ['USF', 'RUT']
MONDAY_RESULTS = ['ATL', 'UNDER', 'NO', 'CHI', 'OVER', 'YES']
SATURDAY_RESULTS = [
    'ILLINOIS',
    'MISSOURI',
    'INDIANA',
    'OKLAHOMA',
    'GEORGIA',
    'BYU'
]
SUNDAY_RESULTS = [
    'NYJ',
    'PIT',
    'MIA',
    'NE',
    'LAR',
    'SEA',
    'TB',
    'KC'
]
DATA_OVERRIDE_PATH = DATA_DIR / 'picks' / 'thursday_picks.json'

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
    HARD_PICKS = {
        "kylejkz11@gmail.com": ["PHI", "OVER", "YES"],
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
    if 'FRIDAY_PICKS' in globals():
        base.update(FRIDAY_PICKS.keys())
    if 'SATURDAY_PICKS' in globals():
        base.update(SATURDAY_PICKS.keys())
    if 'SUNDAY_PICKS' in globals():
        base.update(SUNDAY_PICKS.keys())
    if 'MONDAY_PICKS' in globals():
        base.update(MONDAY_PICKS.keys())
    return sorted(base)

ALL_USERS = _aggregate_all_users()

from .utils import _check_pin

def _refresh_all_users():
    global ALL_USERS
    ALL_USERS = _aggregate_all_users()

# --- Friday picks ---
FRIDAY_FILE = DATA_DIR / 'picks' / 'friday_picks.json'
FRIDAY_CSV_LOG = DATA_DIR / 'picks' / 'friday_picks_log.csv'
FRIDAY_LOCK_FILE = DATA_DIR / 'picks' / 'friday_locked.json'
FRIDAY_LOCK_STATUS = DATA_DIR / 'picks' / 'friday_lock_status.json'
FRIDAY_SEED_CSV = DATA_DIR / 'picks' / 'Fri_Picks.csv'
FRIDAY_LABELS = [
    'NCAAF: USF +1.5 @ UNT (pick team)',
    'NCAAF: Rutgers +10.5 @ WASH (pick team)'
]

FRIDAY_SCHEDULE = [
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
        'start': '2025-10-10T23:59:00Z'
    }
]

def _seed_friday_from_csv():
    if not FRIDAY_SEED_CSV.exists():
        return {}
    seeded = {}
    try:
        with FRIDAY_SEED_CSV.open('r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        if not lines:
            return {}
        header = [h.strip().lower() for h in lines[0].split(',')]
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 1 + len(FRIDAY_LABELS):
                continue
            email = parts[0].lower()
            picks = [p.upper() for p in parts[1:1+len(FRIDAY_LABELS)]]
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
        pass

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
    if not FRIDAY_CSV_LOG.exists():
        return FRIDAY_PICKS.copy()
    latest = {}
    try:
        with FRIDAY_CSV_LOG.open('r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        if not lines:
            return FRIDAY_PICKS.copy()
        header = lines[0].split(',')
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
FRIDAY_PICKS = _seeded_csv if _seeded_csv else _load_friday()
FRIDAY_PICKS, _merged = _merge_seed_into_friday(FRIDAY_PICKS)

@picks_bp.route('/api/admin/friday/seed', methods=['POST'])
def admin_friday_seed():
    global FRIDAY_PICKS
    before = len(FRIDAY_PICKS)
    FRIDAY_PICKS, changed = _merge_seed_into_friday(FRIDAY_PICKS)
    after = len(FRIDAY_PICKS)
    return jsonify({ 'ok': True, 'changed': changed, 'countBefore': before, 'countAfter': after })

@picks_bp.route('/api/picks/friday/labels')
def friday_labels():
    return jsonify({ 'ok': True, 'labels': FRIDAY_LABELS })

@picks_bp.route('/api/picks/friday/get')
def friday_get():
    email = (request.args.get('email') or '').strip().lower()
    picks = FRIDAY_PICKS.get(email)
    return jsonify({ 'ok': True, 'email': email, 'picks': picks })

@picks_bp.route('/api/picks/friday/submit', methods=['POST'])
def friday_submit():
    from .utils import _load_allowed_emails
    ALLOWED_EMAILS = _load_allowed_emails()
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

@picks_bp.route('/api/picks/friday/all')
def friday_all():
    counts = [ {}, {} ]
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

@picks_bp.route('/api/picks/friday/status')
def friday_status():
    _refresh_all_users()
    submitted = sorted(FRIDAY_PICKS.keys())
    missing = [u for u in ALL_USERS if u not in FRIDAY_PICKS]
    return jsonify({ 'ok': True, 'submitted': submitted, 'missing': missing, 'submittedCount': len(submitted), 'missingCount': len(missing), 'locked': _is_friday_locked() })

@picks_bp.route('/api/picks/friday/lock', methods=['POST'])
def friday_lock():
    if _is_friday_locked():
        data = _load_friday_locked()
        return jsonify({ 'ok': True, 'alreadyLocked': True, 'lockedAt': data.get('lockedAt'), 'count': len(data.get('picks', {})) })
    snapshot = _snapshot_latest_from_log()
    if not snapshot:
        snapshot = FRIDAY_PICKS.copy()
    if not _write_friday_locked(snapshot):
        return jsonify({ 'ok': False, 'error': 'lock_write_failed' }), 500
    return jsonify({ 'ok': True, 'locked': True, 'count': len(snapshot) })

@picks_bp.route('/api/picks/friday/lock/status')
def friday_lock_status():
    st = _load_friday_lock_status()
    if st.get('locked'):
        data = _load_friday_locked()
        st['count'] = len(data.get('picks', {}))
        st['emails'] = sorted(data.get('picks', {}).keys())
    return jsonify({ 'ok': True, **st })

@picks_bp.route('/api/picks/export')
def picks_export():
    day = (request.args.get('day') or '').strip().lower()
    if day.startswith('thu'):
        header = ['email'] + [f'pick{i+1}' for i in range(len(RESULTS))]
        lines = [','.join(header)]
        for email in sorted(HARD_PICKS.keys()):
            row = [email] + HARD_PICKS[email]
            lines.append(','.join(_csv_escape(str(v)) for v in row))
        csv_data = '\n'.join(lines) + '\n'
        return current_app.response_class(csv_data, mimetype='text/csv')
    if day.startswith('fri'):
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
        return current_app.response_class(csv_data, mimetype='text/csv')
    return jsonify({ 'ok': False, 'error': 'unsupported_day' }), 400

@picks_bp.route('/api/picks/friday/log')
def friday_log():
    if not FRIDAY_CSV_LOG.exists():
        return jsonify({ 'ok': True, 'empty': True, 'message': 'no_log' })
    try:
        with FRIDAY_CSV_LOG.open('r', encoding='utf-8') as f:
            content = f.read()
        return current_app.response_class(content, mimetype='text/csv')
    except Exception as e:
        return jsonify({ 'ok': False, 'error': 'log_read_failed', 'detail': str(e) }), 500

@picks_bp.route('/api/picks/friday/log/info')
def friday_log_info():
    if not FRIDAY_CSV_LOG.exists():
        return jsonify({ 'ok': True, 'exists': False })
    try:
        stat = FRIDAY_CSV_LOG.stat()
        size = stat.st_size
        mtime = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(stat.st_mtime))
        with FRIDAY_CSV_LOG.open('r', encoding='utf-8') as f:
            lines = f.read().strip().splitlines()
        rows = max(0, len(lines) - 1) if lines else 0
        return jsonify({ 'ok': True, 'exists': True, 'sizeBytes': size, 'modified': mtime, 'rowCount': rows })
    except Exception as e:
        return jsonify({ 'ok': False, 'error': 'log_info_failed', 'detail': str(e) }), 500

@picks_bp.route('/api/picks/friday/log/latest')
def friday_log_latest():
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

# ------------------ Saturday (new) ------------------
SATURDAY_LABELS = [
    'NCAAF: Ohio St -15.5 @ Illinois (pick team)',
    'NCAAF: Alabama -3.5 @ Missouri (pick team)',
    'NCAAF: Indiana +7.5 @ Oregon (pick team)',
    'NCAAF: Oklahoma +2.5 @ Texas (pick team)',
    'NCAAF: Georgia -4.5 @ Auburn (pick team)',
    'NCAAF: BYU -2.5 @ Arizona (pick team)'
]

SATURDAY_SCHEDULE = [
    { 'sport':'NCAAF', 'eventId': '401752865', 'away':'Ohio State', 'awayAbbr':'OHST', 'home':'Illinois', 'homeAbbr':'ILL', 'lineHome': +15.5, 'total': None, 'start':'2025-10-11T16:00:00Z' },
    { 'sport':'NCAAF', 'eventId': '401752734', 'away':'Alabama', 'awayAbbr':'ALA', 'home':'Missouri', 'homeAbbr':'MIZ', 'lineHome': +3.5, 'total': None, 'start':'2025-10-11T16:00:00Z' },
    { 'sport':'NCAAF', 'eventId': '401752870', 'away':'Indiana', 'awayAbbr':'IND', 'home':'Oregon', 'homeAbbr':'ORE', 'lineHome': -7.5, 'total': None, 'start':'2025-10-11T19:30:00Z' },
    { 'sport':'NCAAF', 'eventId': '401752736', 'away':'Oklahoma', 'awayAbbr':'OKLA', 'home':'Texas', 'homeAbbr':'TEX', 'lineHome': -2.5, 'total': None, 'start':'2025-10-11T19:30:00Z' },
    { 'sport':'NCAAF', 'eventId': '401752867', 'away':'Georgia', 'awayAbbr':'UGA', 'home':'Auburn', 'homeAbbr':'AUB', 'lineHome': +4.5, 'total': None, 'start':'2025-10-11T23:30:00Z' },
    { 'sport':'NCAAF', 'eventId': '401756916', 'away':'BYU', 'awayAbbr':'BYU', 'home':'Arizona', 'homeAbbr':'ARIZ', 'lineHome': +2.5, 'total': None, 'start':'2025-10-12T00:00:00Z' }
]

SATURDAY_FILE = DATA_DIR / 'picks' / 'saturday_picks.json'
SATURDAY_LOCK_FILE = DATA_DIR / 'picks' / 'saturday_locked.json'
SATURDAY_LOCK_STATUS = DATA_DIR / 'picks' / 'saturday_lock_status.json'

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
            SATURDAY_PICKS[em] = ['']*len(SATURDAY_LABELS)
            picks = SATURDAY_PICKS[em]
            changed=True
        if len(picks) < len(SATURDAY_LABELS):
            while len(picks) < len(SATURDAY_LABELS): picks.append('')
            changed=True
    if changed:
        try: _save_saturday(SATURDAY_PICKS)
        except Exception: pass
_apply_saturday_backfill()

def _force_first_two_targets():
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
            snap_norm = snap[:len(SATURDAY_LABELS)] + ['']*max(0, len(SATURDAY_LABELS)-len(snap))
            for i in (0,1):
                if i < len(cur) and not cur[i] and snap_norm[i]:
                    cur[i] = str(snap_norm[i]).strip().upper()
                    changed = True
        if len(cur) < len(SATURDAY_LABELS):
            cur.extend(['']*(len(SATURDAY_LABELS)-len(cur)))
            changed = True
    if changed:
        _save_saturday(SATURDAY_PICKS)
        _refresh_all_users()
    return changed

_force_first_two_targets()

_SATURDAY_FILE_MTIME = SATURDAY_FILE.stat().st_mtime if SATURDAY_FILE.exists() else None

try:
    if not SATURDAY_PICKS and SATURDAY_FILE.exists():
        data = _load_saturday()
        if isinstance(data, dict) and data:
            SATURDAY_PICKS = data
            _enforce_full_saturday()
except Exception:
    pass

def _maybe_reload_saturday():
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
        if _force_first_two_targets():
            changed = True
        if changed:
            _save_saturday(SATURDAY_PICKS)
            _refresh_all_users()
        return changed
    except Exception:
        return False

SATURDAY_GAME_LOCKS_FILE = DATA_DIR / 'picks' / 'saturday_game_locks.json'

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
    try:
        if ts.endswith('Z'):
            ts = ts[:-1]
        date_part, time_part = ts.split('T')
        y,m,d = [int(x) for x in date_part.split('-')]
        hh,mm,ss = [int(x) for x in time_part.split(':')]
        import calendar
        return calendar.timegm((y,m,d,hh,mm,ss,0,0,0))
    except Exception:
        return None

_SATURDAY_MANUAL_LOCKS = _load_saturday_game_locks()

def _is_saturday_game_locked(index: int):
    return False

def _saturday_effective_locks():
    return [{ 'index': i, 'manualLocked': False, 'started': False, 'effectiveLocked': False, 'start': g.get('start') } for i,g in enumerate(SATURDAY_SCHEDULE)]

@picks_bp.route('/api/picks/saturday/labels')
def saturday_labels():
    return jsonify({ 'ok': True, 'labels': SATURDAY_LABELS })

@picks_bp.route('/api/picks/saturday/get')
def saturday_get():
    email = (request.args.get('email') or '').strip().lower()
    picks = SATURDAY_PICKS.get(email)
    return jsonify({ 'ok': True, 'email': email, 'picks': picks })

@picks_bp.route('/api/picks/saturday/submit', methods=['POST'])
def saturday_submit():
    from .utils import _load_allowed_emails
    ALLOWED_EMAILS = _load_allowed_emails()
    payload = request.get_json(force=True, silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    picks = payload.get('picks') or []
    pin = str(payload.get('pin') or '').strip()
    if _is_saturday_locked():
        return jsonify({ 'ok': False, 'error': 'day_locked' }), 403
    if not email:
        return jsonify({ 'ok': False, 'error': 'email_required' }), 400
    if not isinstance(picks, list):
        return jsonify({ 'ok': False, 'error': 'invalid_picks_type' }), 400
    if len(picks) > len(SATURDAY_LABELS):
        picks = picks[:len(SATURDAY_LABELS)]
    if len(picks) < len(SATURDAY_LABELS):
        picks = picks + [''] * (len(SATURDAY_LABELS) - len(picks))
    if email not in ALLOWED_EMAILS:
        return jsonify({ 'ok': False, 'error': 'unauthorized_email' }), 403
    if not _check_pin(email, pin):
        return jsonify({ 'ok': False, 'error': 'invalid_pin' }), 403
    updated = [str(val or '').strip().upper() for val in picks]
    SATURDAY_PICKS[email] = updated
    if not _save_saturday(SATURDAY_PICKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    return jsonify({ 'ok': True, 'saved': True, 'lockedGames': [] })

@picks_bp.route('/api/picks/saturday/status')
def saturday_status():
    _maybe_reload_saturday()
    _refresh_all_users()
    submitted = sorted(SATURDAY_PICKS.keys())
    missing = [u for u in ALL_USERS if u not in SATURDAY_PICKS]
    return jsonify({ 'ok': True, 'submitted': submitted, 'missing': missing, 'submittedCount': len(submitted), 'missingCount': len(missing), 'locked': _is_saturday_locked(), 'gameLocks': _saturday_effective_locks() })

@picks_bp.route('/api/picks/saturday/lock', methods=['POST'])
def saturday_lock():
    if _is_saturday_locked():
        data = _load_saturday_locked()
        return jsonify({ 'ok': True, 'alreadyLocked': True, 'lockedAt': data.get('lockedAt'), 'count': len(data.get('picks', {})) })
    snapshot = SATURDAY_PICKS.copy()
    if not _write_saturday_locked(snapshot):
        return jsonify({ 'ok': False, 'error': 'lock_write_failed' }), 500
    return jsonify({ 'ok': True, 'locked': True, 'count': len(snapshot) })

@picks_bp.route('/api/picks/saturday/unlock', methods=['POST'])
def saturday_unlock():
    token = request.args.get('token') or request.headers.get('X-Admin-Token')
    admin_token = os.environ.get('ADMIN_TOKEN')
    if admin_token and token != admin_token:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
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

@picks_bp.route('/api/picks/saturday/lock/status')
def saturday_lock_status():
    st = _load_saturday_lock_status()
    if st.get('locked'):
        data = _load_saturday_locked()
        st['count'] = len(data.get('picks', {}))
        st['emails'] = sorted(data.get('picks', {}).keys())
    return jsonify({ 'ok': True, **st })

@picks_bp.route('/api/picks/saturday/all')
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

# ------------------ Sunday (new) ------------------
SUNDAY_LABELS = [
    'NFL: DEN -6.5 @ NYJ (pick team)',
    'NFL: CLE +6.5 @ PIT (pick team)',
    'NFL: LAC -3.5 @ MIA (pick team)',
    'NFL: NE -3.5 @ NO (pick team)',
    'NFL: LAR -7.5 @ BAL (pick team)',
    'NFL: SEA -1.5 @ JAX (pick team)',
    'NFL: SF +3.5 @ TB (pick team)',
    'NFL: DET +2.5 @ KC (pick team)'
]

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

SUNDAY_FILE = DATA_DIR / 'picks' / 'sunday_picks.json'
SUNDAY_CSV_LOG = DATA_DIR / 'picks' / 'sunday_picks_log.csv'
SUNDAY_LOCK_FILE = DATA_DIR / 'picks' / 'sunday_locked.json'
SUNDAY_LOCK_STATUS = DATA_DIR / 'picks' / 'sunday_lock_status.json'

SUNDAY_PREFILL_DEFAULT = {
    "scire.ben@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "max1solov@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "amacdonald171@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "williamjabbott22@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "jakelehman100@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "timjbohlman@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "wyaggy3@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "sam.scire@hotmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "kylejkz11@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "samuel.lehman3337@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "goodnoughdylan@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "shawnscottcarl@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "jlindsey3428@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "hankrudden@yahoo.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "soligonaustin@outlook.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "finsmaniac1551@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "jaked9577@yahoo.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"],
    "sam.scire@gmail.com": ["NYJ", "PIT", "MIA", "NE", "LAR", "SEA", "TB", "KC"]
}

def _bootstrap_sunday_prefill_if_missing():
    try:
        if not SUNDAY_FILE.exists():
            SUNDAY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with SUNDAY_FILE.open('w', encoding='utf-8') as f:
                json.dump(SUNDAY_PREFILL_DEFAULT, f, indent=2)
            return True
    except Exception:
        pass
    return False

_bootstrap_sunday_prefill_if_missing()

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

SUNDAY_AUTOFILL_META_FILE = DATA_DIR / 'picks' / 'sunday_autofill_meta.json'
def _load_sunday_autofill_meta():
    if SUNDAY_AUTOFILL_META_FILE.exists():
        try:
            with SUNDAY_AUTOFILL_META_FILE.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                out = {}
                for email, flags in data.items():
                    if isinstance(flags, list):
                        adj = [bool(x) for x in flags[:len(SUNDAY_LABELS)]]
                        while len(adj) < len(SUNDAY_LABELS):
                            adj.append(False)
                        out[email] = adj
                return out
        except Exception:
            return {}
    return {}

def _save_sunday_autofill_meta():
    try:
        SUNDAY_AUTOFILL_META_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SUNDAY_AUTOFILL_META_FILE.open('w', encoding='utf-8') as f:
            json.dump(SUNDAY_AUTOFILL_META, f, indent=2)
        return True
    except Exception:
        return False

SUNDAY_AUTOFILL_META = _load_sunday_autofill_meta()

def _sunday_backfill_game0_nyj():
    try:
        changed = False
        for email, sat in SATURDAY_PICKS.items():
            picks = SUNDAY_PICKS.get(email)
            if not isinstance(picks, list):
                picks = ['']*len(SUNDAY_LABELS)
                SUNDAY_PICKS[email] = picks
                changed = True
            if len(picks) < len(SUNDAY_LABELS):
                picks.extend(['']*(len(SUNDAY_LABELS)-len(picks)))
                changed = True
            if not picks[0]:
                picks[0] = 'NYJ'
                flags = SUNDAY_AUTOFILL_META.get(email)
                if not isinstance(flags, list):
                    flags = [False]*len(SUNDAY_LABELS)
                if len(flags) < len(SUNDAY_LABELS):
                    flags.extend([False]*(len(SUNDAY_LABELS)-len(flags)))
                if not flags[0]:
                    flags[0] = True
                    SUNDAY_AUTOFILL_META[email] = flags
                changed = True
        if changed:
            _save_sunday(SUNDAY_PICKS)
            _save_sunday_autofill_meta()
            _refresh_all_users()
        return changed
    except Exception:
        return False

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

SUNDAY_GAME_LOCKS_FILE = DATA_DIR / 'picks' / 'sunday_game_locks.json'

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

@picks_bp.route('/api/picks/sunday/labels')
def sunday_labels():
    return jsonify({ 'ok': True, 'labels': SUNDAY_LABELS })

@picks_bp.route('/api/picks/sunday/get')
def sunday_get():
    email = (request.args.get('email') or '').strip().lower()
    return jsonify({ 'ok': True, 'email': email, 'picks': SUNDAY_PICKS.get(email) })

@picks_bp.route('/api/picks/sunday/submit', methods=['POST'])
def sunday_submit():
    from .utils import _load_allowed_emails
    ALLOWED_EMAILS = _load_allowed_emails()
    payload = request.get_json(force=True, silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    picks = payload.get('picks') or []
    pin = str(payload.get('pin') or '').strip()

    if not email:
        return jsonify({ 'ok': False, 'error': 'email_required' }), 400
    if not isinstance(picks, list):
        return jsonify({ 'ok': False, 'error': 'invalid_picks_type' }), 400
    if email not in ALLOWED_EMAILS:
        return jsonify({ 'ok': False, 'error': 'unauthorized_email' }), 403
    if not _check_pin(email, pin):
        return jsonify({ 'ok': False, 'error': 'invalid_pin' }), 403

    # Normalize picks length
    if len(picks) > len(SUNDAY_LABELS):
        picks = picks[:len(SUNDAY_LABELS)]
    if len(picks) < len(SUNDAY_LABELS):
        picks.extend([''] * (len(SUNDAY_LABELS) - len(picks)))

    current_picks = SUNDAY_PICKS.get(email, [''] * len(SUNDAY_LABELS))
    # Prevent overwriting locked games
    for i in range(len(SUNDAY_LABELS)):
        if _is_sunday_game_locked(i):
            picks[i] = current_picks[i]

    updated = [str(val or '').strip().upper() for val in picks]
    SUNDAY_PICKS[email] = updated

    # Handle autofill meta
    flags = SUNDAY_AUTOFILL_META.get(email, [])
    if len(flags) < len(SUNDAY_LABELS):
        flags.extend([False]*(len(SUNDAY_LABELS)-len(flags)))

    user_changed_autofill = False
    for i, val in enumerate(updated):
        if val and i < len(flags) and flags[i]:
            flags[i] = False
            user_changed_autofill = True

    if user_changed_autofill or email not in SUNDAY_AUTOFILL_META:
        SUNDAY_AUTOFILL_META[email] = flags
        _save_sunday_autofill_meta()

    if not _save_sunday(SUNDAY_PICKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500

    _append_sunday_csv(email, updated)

    return jsonify({ 'ok': True, 'saved': True, 'lockedGames': [i for i in range(len(SUNDAY_LABELS)) if _is_sunday_game_locked(i)] })

@picks_bp.route('/api/picks/sunday/status')
def sunday_status():
    _maybe_reload_sunday(); _sunday_backfill_game0_nyj()
    _refresh_all_users()
    submitted = sorted(SUNDAY_PICKS.keys())
    missing = [u for u in ALL_USERS if u not in SUNDAY_PICKS]
    return jsonify({ 'ok': True, 'submitted': submitted, 'missing': missing, 'submittedCount': len(submitted), 'missingCount': len(missing), 'gameLocks': _sunday_effective_locks() })

@picks_bp.route('/api/picks/sunday/all')
def sunday_all():
    _maybe_reload_sunday(); _sunday_backfill_game0_nyj()
    counts = [ {} for _ in range(len(SUNDAY_LABELS)) ]
    for email, picks in SUNDAY_PICKS.items():
        for i,val in enumerate(picks):
            if not val: continue
            d = counts[i]; d[val] = d.get(val,0)+1
    return jsonify({ 'ok': True, 'labels': SUNDAY_LABELS, 'totalSubmissions': len(SUNDAY_PICKS), 'picks': SUNDAY_PICKS, 'counts': counts, 'gameLocks': _sunday_effective_locks() })

@picks_bp.route('/api/admin/sunday/autofill_report')
def admin_sunday_autofill_report():
    token = request.args.get('token') or request.headers.get('X-Admin-Token')
    admin_token = os.environ.get('ADMIN_TOKEN')
    if admin_token and token != admin_token:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    _maybe_reload_sunday(); _sunday_backfill_game0_nyj()
    for email in list(SUNDAY_PICKS.keys()):
        flags = SUNDAY_AUTOFILL_META.get(email)
        if not isinstance(flags, list):
            flags = [False]*len(SUNDAY_LABELS)
        if len(flags) < len(SUNDAY_LABELS):
            flags.extend([False]*(len(SUNDAY_LABELS)-len(flags)))
        if len(flags) > len(SUNDAY_LABELS):
            flags = flags[:len(SUNDAY_LABELS)]
        SUNDAY_AUTOFILL_META[email] = flags
    entries = []
    for email, picks in SUNDAY_PICKS.items():
        flags = SUNDAY_AUTOFILL_META.get(email, [False]*len(SUNDAY_LABELS))
        auto_idxs = [i for i, f in enumerate(flags) if f and picks[i]]
        entries.append({
            'email': email,
            'picks': picks,
            'autoFilledIndices': auto_idxs,
            'autoFilledCount': len(auto_idxs),
            'manualCount': sum(1 for i,v in enumerate(picks) if v and not flags[i]),
            'flags': flags
        })
    return jsonify({ 'ok': True, 'labels': SUNDAY_LABELS, 'entries': entries, 'version': 'week-multi-24' })

def _admin_auth_sunday(payload):
    email = (payload.get('email') or '').strip().lower()
    pin = str(payload.get('pin') or '').strip()
    if email != 'scire.ben@gmail.com': return False, 'not_admin'
    if not _check_pin(email, pin): return False, 'invalid_pin'
    return True, email

@picks_bp.route('/api/picks/sunday/game_locks')
def sunday_game_locks():
    return jsonify({ 'ok': True, 'locks': _sunday_effective_locks() })

@picks_bp.route('/api/picks/sunday/lock_game', methods=['POST'])
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

@picks_bp.route('/api/picks/sunday/unlock_game', methods=['POST'])
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
    if email != 'scire.ben@gmail.com':
        return False, 'not_admin'
    if not _check_pin(email, pin):
        return False, 'invalid_pin'
    return True, email

@picks_bp.route('/api/picks/saturday/game_locks')
def saturday_game_locks():
    return jsonify({ 'ok': True, 'locks': _saturday_effective_locks() })

@picks_bp.route('/api/picks/saturday/lock_game', methods=['POST'])
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

@picks_bp.route('/api/picks/saturday/unlock_game', methods=['POST'])
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
    if _is_saturday_game_locked(idx) and not _SATURDAY_MANUAL_LOCKS.get(str(idx)):
        return jsonify({ 'ok': False, 'error': 'started_auto_lock' }), 409
    _SATURDAY_MANUAL_LOCKS[str(idx)] = False
    if str(idx) in _SATURDAY_MANUAL_LOCKS and not _SATURDAY_MANUAL_LOCKS[str(idx)]:
        _SATURDAY_MANUAL_LOCKS.pop(str(idx), None)
    if not _save_saturday_game_locks(_SATURDAY_MANUAL_LOCKS):
        return jsonify({ 'ok': False, 'error': 'persist_failed' }), 500
    return jsonify({ 'ok': True, 'locks': _saturday_effective_locks() })
