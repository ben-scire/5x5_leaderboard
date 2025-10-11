"""Ultra-minimal Thursday-only leaderboard server (fully cleaned version)."""
from flask import Flask, jsonify, send_from_directory, request
import time, os, json, pathlib

VERSION = 'minimal-thu-11'

# Final outcomes for the single Thursday game
RESULTS = ['NYG', 'OVER', 'YES']  # spread winner, total, prop

# Hard-coded authoritative picks (email -> list[str]); may be overridden by file
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

DATA_OVERRIDE_PATH = pathlib.Path('data/picks/thursday_picks.json')

def _load_override():
    if DATA_OVERRIDE_PATH.exists():
        try:
            with DATA_OVERRIDE_PATH.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                cleaned = {}
                for k,v in data.items():
                    if isinstance(v, list) and len(v) == len(RESULTS):
                        cleaned[k] = [str(x).strip().upper() for x in v]
                if cleaned:
                    return cleaned
        except Exception:
            pass
    return None

_override = _load_override()
if _override:
    HARD_PICKS = _override  # type: ignore
    SOURCE = 'file'
else:
    SOURCE = 'embedded'

ALL_USERS = sorted(HARD_PICKS.keys())
TOTAL_POSSIBLE = len(RESULTS)

app = Flask(__name__, static_folder='.', static_url_path='')

# --- Cache control: prevent stale HTML on mobile Safari / iOS ---
# Strategy:
# 1. All HTML responses get no-store headers so updates are always fetched.
# 2. Static assets (css/js) keep cacheable names but we append a ?v=VERSION query in HTML.
#    When you change VERSION constant above, bump ASSET_TAG below or directly edit HTML query strings.

@app.after_request
def _add_cache_headers(resp):
    ct = (resp.mimetype or '').lower()
    if 'text/html' in ct:
        # Strong no-cache for HTML documents
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
    if _is_friday_locked():
        return jsonify({ 'ok': False, 'error': 'locked' }), 403
    if not email:
        return jsonify({ 'ok': False, 'error': 'email_required' }), 400
    if not isinstance(picks, list) or len(picks) != len(FRIDAY_LABELS):
        return jsonify({ 'ok': False, 'error': 'invalid_picks_length' }), 400
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

def compute_scores():
    """Return sorted list of scoreboard entries for all users."""
    entries = []
    for email in ALL_USERS:
        picks = HARD_PICKS[email]
        answered = sum(1 for p in picks if p)
        score = sum(1 for a, b in zip(picks, RESULTS) if a == b)
        entries.append({
            'email': email,
            'score': score,
            'answered': answered,
            'totalPossible': TOTAL_POSSIBLE,
            'perDay': { 'Thu': { 'score': score, 'answered': answered } }
        })
    entries.sort(key=lambda r: (-r['score'], r['answered'], r['email']))
    return entries

@app.route('/api/leaderboard')
def api_leaderboard():
    entries = compute_scores()
    return jsonify({
        'ok': True,
        'dayOrder': ['Thu'],
        'totalPossible': TOTAL_POSSIBLE,
        'entries': entries,
        'generated': int(time.time()*1000)
    })

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
    return jsonify({ 'ok': False, 'error': 'unsupported_day' }), 400

@app.route('/api/debug/thu')
def api_debug_thu():
    entries = compute_scores()[:10]
    slim = [ {k:v for k,v in e.items() if k in ('email','score','answered')} for e in entries ]
    return jsonify({ 'ok': True, 'version': VERSION, 'results': RESULTS, 'sample': slim, 'count': len(ALL_USERS), 'source': SOURCE })

@app.route('/healthz')
def healthz():
    return jsonify({ 'ok': True, 'version': VERSION, 'users': len(ALL_USERS), 'results': RESULTS, 'source': SOURCE })

@app.route('/api/schedule')
def api_schedule():
    """Provide minimal schedule JSON consumed by schedule_init.js for live Friday board."""
    # Thursday left minimal (historical). Only supply Friday picks & games for now.
    days = {
        'Fri': {
            'games': FRIDAY_SCHEDULE,
            'picks': [ { 'label': lbl } for lbl in FRIDAY_LABELS ]
        }
    }
    return jsonify({ 'ok': True, 'version': VERSION, 'days': days })

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
