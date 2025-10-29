"""Bulk email PIN codes to users.

Usage (PowerShell):
  $env:SMTP_HOST='smtp.gmail.com'
  $env:SMTP_PORT='587'
  $env:SMTP_USER='you@gmail.com'
  $env:SMTP_PASS='app_password'
  $env:PIN_FROM='5x5 Picks <you@gmail.com>'
  python scripts/email_pins.py --dry-run   # preview only
  python scripts/email_pins.py             # actually send

You can optionally limit to a single email:
  python scripts/email_pins.py --only someone@example.com

Safety:
- Default is live mode unless --dry-run.
- Retries each email up to 3 times.
"""
from __future__ import annotations
import os, sys, argparse, json, smtplib, time
from email.message import EmailMessage
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / 'data'
PINS_PATH = DATA_DIR / 'picks' / 'pins.json'
SENT_LOG_PATH = DATA_DIR / 'picks' / 'pins_sent_log.json'  # records email -> { pin, firstSent, lastSent, count }

SUBJECT = "Your 5x5 Saturday Pick Submission PIN"
BODY_TEMPLATE = (
    "Hi {user},\n\n"
    "Your 4-digit PIN for submitting Saturday picks is: {pin}\n\n"
    "Go to the leaderboard page and click 'Submit Saturday Picks'. Select your email from the dropdown and enter this PIN. "
    "You can resubmit (overwrite) until picks are locked. Keep this PIN private.\n\n"
    "If you believe you received this in error, ignore it.\n\n"
    "Good luck!\n"
    "-- 5x5 Picks Bot\n"
)

HTML_TEMPLATE = (
    "<p>Hi {user},</p>"
    "<p>Your 4-digit <strong>PIN</strong> for submitting <em>Saturday</em> picks is: <span style=\"font-size:20px;font-weight:700;letter-spacing:2px;\">{pin}</span></p>"
    "<p>Visit the site, open <b>Submit Saturday Picks</b>, choose your email, enter the PIN, make selections, and Save. You may overwrite until lock.</p>"
    "<p style=\"color:#666;\">Keep this PIN private. If you did not expect this message, you can ignore it.</p>"
    "<p>Good luck!<br/>-- 5x5 Picks Bot</p>"
)

def load_pins():
    if not PINS_PATH.exists():
        print("pins.json not found", file=sys.stderr)
        sys.exit(1)
    with PINS_PATH.open('r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        print('pins.json invalid format', file=sys.stderr)
        sys.exit(1)
    return { k.lower(): str(v) for k,v in data.items() }


def build_message(email: str, pin: str, sender: str) -> EmailMessage:
    msg = EmailMessage()
    msg['Subject'] = SUBJECT
    msg['From'] = sender
    msg['To'] = email
    user_name = email.split('@')[0]
    text = BODY_TEMPLATE.format(user=user_name, pin=pin)
    html = HTML_TEMPLATE.format(user=user_name, pin=pin)
    msg.set_content(text)
    msg.add_alternative(f"<html><body>{html}</body></html>", subtype='html')
    return msg


def _load_sent_log():
    if SENT_LOG_PATH.exists():
        try:
            with SENT_LOG_PATH.open('r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
    return {}

def _save_sent_log(data: dict):
    try:
        SENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with SENT_LOG_PATH.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def send_all(pins: dict, sender: str, host: str, port: int, user: str, password: str, dry_run: bool, only: str | None, skip_already: bool):
    targets = pins
    if only:
        only_l = only.lower()
        if only_l not in pins:
            print(f"Email {only} not in pins list.")
            return
        targets = { only_l: pins[only_l] }
    sent_log = _load_sent_log()
    if skip_already:
        filtered = { e:p for e,p in targets.items() if e not in sent_log }
        print(f"Skipping {len(targets)-len(filtered)} already-sent emails (use without --skip-already to resend).")
        targets = filtered
    print(f"Preparing to {'preview' if dry_run else 'send'} {len(targets)} emails ...")
    if dry_run:
        for e,p in targets.items():
            msg = build_message(e,p,sender)
            print('-'*40)
            print('TO:', e)
            print(msg.get_content())
        print('\n(DRY RUN) No emails sent.')
        return
    # Live send
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        sent = 0
        for e,p in targets.items():
            msg = build_message(e,p,sender)
            for attempt in range(1,4):
                try:
                    smtp.send_message(msg)
                    sent += 1
                    print(f"Sent to {e} (pin {p})")
                    now_iso = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    if e in sent_log:
                        rec = sent_log[e]
                        rec['lastSent'] = now_iso
                        rec['count'] = rec.get('count',1) + 1
                    else:
                        sent_log[e] = { 'pin': p, 'firstSent': now_iso, 'lastSent': now_iso, 'count': 1 }
                    time.sleep(0.4)  # mild pacing
                    break
                except Exception as ex:
                    print(f"Attempt {attempt} failed for {e}: {ex}")
                    time.sleep(1.0)
        print(f"Done. Sent {sent}/{len(targets)} emails.")
    _save_sent_log(sent_log)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='Print emails instead of sending')
    ap.add_argument('--only', help='Send only to a single email')
    ap.add_argument('--skip-already', action='store_true', help='Skip emails already present in sent log')
    args = ap.parse_args()

    pins = load_pins()
    host = os.environ.get('SMTP_HOST')
    port = int(os.environ.get('SMTP_PORT') or '587')
    user = os.environ.get('SMTP_USER')
    password = os.environ.get('SMTP_PASS')
    sender = os.environ.get('PIN_FROM') or user or 'no-reply@example.com'

    if not args.dry_run:
        missing = [name for name,val in [('SMTP_HOST',host),('SMTP_USER',user),('SMTP_PASS',password)] if not val]
        if missing:
            print(f"Missing required SMTP env vars: {', '.join(missing)}. Set them or use --dry-run to preview.", file=sys.stderr)
            print("Example (PowerShell): $env:SMTP_HOST='smtp.gmail.com'; $env:SMTP_USER='you@gmail.com'; $env:SMTP_PASS='app_password'", file=sys.stderr)
            sys.exit(2)

    send_all(pins, sender, host, port, user, password, args.dry_run, args.only, args.skip_already)

if __name__ == '__main__':
    main()
