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
    return jsonify({ 'ok': False, 'error': 'unsupported_day' }), 400

@app.route('/api/debug/thu')
def api_debug_thu():
    entries = compute_scores()[:10]
    slim = [ {k:v for k,v in e.items() if k in ('email','score','answered')} for e in entries ]
    return jsonify({ 'ok': True, 'version': VERSION, 'results': RESULTS, 'sample': slim, 'count': len(ALL_USERS), 'source': SOURCE })

@app.route('/healthz')
def healthz():
    return jsonify({ 'ok': True, 'version': VERSION, 'users': len(ALL_USERS), 'results': RESULTS, 'source': SOURCE })

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
