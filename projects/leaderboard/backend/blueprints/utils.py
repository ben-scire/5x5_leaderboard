import json
import pathlib
from .picks import ALL_USERS

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / 'data'

PINS_FILE = DATA_DIR / 'picks' / 'pins.json'
ALLOWED_EMAILS_FILE = DATA_DIR / 'allowed_emails.json'
ACTIVE_EMAILS_FILE = DATA_DIR / 'active_emails.json'

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
PIN_MAP = { k:v for k,v in PIN_MAP.items() if k in ALLOWED_EMAILS }

def _check_pin(email: str, pin: str):
    return PIN_MAP.get(email.lower()) == pin

def _norm_team(val: str):
    if not val: return ''
    v = val.strip().upper()
    canonical = {
        'OHIO STATE','MISSOURI','ILLINOIS','ALABAMA','INDIANA','OREGON','OKLAHOMA','TEXAS','GEORGIA','AUBURN','BYU','ARIZONA'
    }
    if v in canonical:
        return v
    alias = {
        'OHIO':'OHIO',
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
    if v == 'OHIO ST': return 'OHIO STATE'
    if v == 'MIZ': return 'MISSOURI'
    if v == 'IND': return 'INDIANA'
    parts = v.replace('&',' ').replace('.',' ').split()
    for i,p in enumerate(parts):
        if p == 'OHIO' and i+1 < len(parts) and parts[i+1] == 'ST':
            parts[i] = 'OHIO STATE'
            parts.pop(i+1)
            break
    v2 = ' '.join(alias.get(p, p) for p in parts)
    if v2 in alias:
        v2 = alias[v2]
    return v2
