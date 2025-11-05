import json, sys, time, os
import urllib.request, urllib.error

BASE = os.environ.get('LB_BASE', 'http://localhost:8000')
ADMIN_EMAIL = os.environ.get('LB_ADMIN_EMAIL', 'scire.ben@gmail.com')
ADMIN_PHRASE = os.environ.get('LB_ADMIN_PHRASE', 'admin')  # only used if needing schedule reload
TEST_PASSWORD = os.environ.get('LB_TEST_PASSWORD', 'LocalTest123')

# Simple helpers

def post(path, data=None, token=None):
    url = BASE + path
    payload = None
    if data is not None:
        payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, method='POST')
    hdrs = {'Content-Type': 'application/json'}
    if token:
        hdrs['X-Admin-Token'] = token
    for k,v in hdrs.items():
        req.add_header(k,v)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.getcode(), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'error':'http_error','detail':body}
    except Exception as e:
        return 0, {'error':'request_failed','detail':str(e)}

def get(path, token=None):
    url = BASE + path
    req = urllib.request.Request(url, method='GET')
    if token:
        req.add_header('X-Admin-Token', token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.getcode(), json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            return e.code, json.loads(body)
        except Exception:
            return e.code, {'error':'http_error','detail':body}
    except Exception as e:
        return 0, {'error':'request_failed','detail':str(e)}

def main():
    time.sleep(5)
    summary = []

    # 1. Schedule
    code, sched = get('/api/schedule')
    summary.append(('schedule', code, 'days=' + str(len(sched.get('days', {}))) ))

    # 2. Get admin pin
    code, pins = get('/api/pins/admin')
    pin = None
    if code == 200 and pins.get('ok'):
        pin = pins.get('pins', {}).get(ADMIN_EMAIL)
        if pin:
            summary.append(('auth', code, 'pin_retrieved'))
        else:
            summary.append(('auth', code, 'pin_missing'))
            print('FAILED auth; cannot continue')
            for row in summary: print(row)
            sys.exit(1)
    else:
        summary.append(('auth', code, 'failed'))
        print('FAILED auth; cannot continue')
        for row in summary: print(row)
        sys.exit(1)

    # 3. Pick get for Sat (if present)
    day = 'Sat'
    code, sat = get(f'/api/picks/saturday/get?email={ADMIN_EMAIL}', token=pin)
    if code == 200 and sat.get('ok'):
        summary.append(('picks_get_'+day, code, f"len={len(sat.get('picks', []))}"))
    else:
        summary.append(('picks_get_'+day, code, 'missing'))

    # 4. Leaderboard
    code, board = get('/api/leaderboard')
    if code == 200 and board.get('ok'):
        summary.append(('leaderboard', code, f"entries={len(board.get('entries', []))}"))
    else:
        summary.append(('leaderboard', code, 'fail'))

    # 5. Admin all picks
    code, allp = get('/api/picks/saturday/all', token=pin)
    summary.append(('admin_all_picks', code, f"days={len((allp.get('picks') or {}))}"))

    # 6. Save a dummy unchanged Sat picks submission (echo existing)
    if sat.get('picks'):
        save_payload = {'email': ADMIN_EMAIL, 'picks': sat['picks'], 'pin': pin}
        code, save_resp = post('/api/picks/saturday/submit', save_payload, token=pin)
        summary.append(('picks_save_'+day, code, save_resp.get('error','ok')))

    print('\nSMOKE TEST SUMMARY:')
    for row in summary:
        print(' -', row)

if __name__ == '__main__':
    main()
