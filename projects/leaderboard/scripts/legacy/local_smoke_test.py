import json, sys, time, os
import urllib.request, urllib.error

BASE = os.environ.get('LB_BASE', 'http://localhost:8000')
ADMIN_EMAIL = os.environ.get('LB_ADMIN_EMAIL', 'scire.ben@gmail.com')
ADMIN_PHRASE = os.environ.get('LB_ADMIN_PHRASE', 'admin')  # only used if needing schedule reload
TEST_PASSWORD = os.environ.get('LB_TEST_PASSWORD', 'LocalTest123')

# Simple helpers

def post(path, data=None, headers=None):
    url = BASE + path
    payload = None
    if data is not None:
        payload = json.dumps(data).encode()
    req = urllib.request.Request(url, data=payload, method='POST')
    hdrs = {'Content-Type': 'application/json'}
    if headers:
        hdrs.update(headers)
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

def get(path, headers=None):
    url = BASE + path
    req = urllib.request.Request(url, method='GET')
    if headers:
        for k,v in headers.items():
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

def main():
    summary = []

    # 1. Schedule
    code, sched = get('/api/schedule')
    summary.append(('schedule', code, 'days=' + str(len(sched.get('days', {}))) ))

    # 2. Create or login admin user
    code, resp = post('/api/auth/create', {'email': ADMIN_EMAIL, 'password': TEST_PASSWORD})
    token = None
    if code == 200 and resp.get('ok'):
        token = resp.get('token')
        summary.append(('auth_create', code, 'created'))
    else:
        # try login
        code2, resp2 = post('/api/auth/login', {'email': ADMIN_EMAIL, 'password': TEST_PASSWORD})
        if code2 == 200 and resp2.get('ok'):
            token = resp2.get('token')
            summary.append(('auth_login', code2, 'logged_in'))
        else:
            summary.append(('auth', code2, 'failed'))
            print('FAILED auth; cannot continue')
            for row in summary: print(row)
            sys.exit(1)

    headers = {'Authorization': f'Bearer {token}'}

    # 3. Pick get for Sat (if present)
    day = 'Sat'
    code, sat = get(f'/api/picks/get?day={day}', headers=headers)
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
    code, allp = get('/api/admin/all_picks', headers=headers)
    summary.append(('admin_all_picks', code, f"days={len((allp.get('days') or {}))}"))

    # 6. Save a dummy unchanged Sat picks submission (echo existing)
    if sat.get('picks'):
        save_payload = {'day': day, 'picks': sat['picks']}
        code, save_resp = post('/api/picks/save', save_payload, headers=headers)
        summary.append(('picks_save_'+day, code, save_resp.get('error','ok')))

    print('\nSMOKE TEST SUMMARY:')
    for row in summary:
        print(' -', row)

if __name__ == '__main__':
    main()
