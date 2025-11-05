from flask import Blueprint, jsonify, request
import os
import json
from .utils import ALLOWED_EMAILS, PIN_MAP, _load_allowed_emails

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/pins/emails')
def api_pins_emails():
    """Return list of selectable emails (no pins)."""
    return jsonify({ 'ok': True, 'emails': ALLOWED_EMAILS, 'version': 'week-multi-24', 'partialSaturdayAllowed': True })

@auth_bp.route('/api/pins/active', methods=['POST'])
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
    try:
        ACTIVE_EMAILS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ACTIVE_EMAILS_FILE.open('w', encoding='utf-8') as f:
            json.dump(sorted({ e.strip().lower() for e in emails if '@' in e }), f, indent=2)
    except Exception as e:
        return jsonify({ 'ok': False, 'error': 'write_failed', 'detail': str(e) }), 500
    global ALLOWED_EMAILS, PIN_MAP
    ALLOWED_EMAILS = _load_allowed_emails()
    PIN_MAP = { k:v for k,v in PIN_MAP.items() if k in ALLOWED_EMAILS }
    return jsonify({ 'ok': True, 'allowed': ALLOWED_EMAILS, 'count': len(ALLOWED_EMAILS) })

@auth_bp.route('/api/pins/admin')
def api_pins_admin():
    token = request.args.get('token')
    admin_token = os.environ.get('ADMIN_TOKEN')
    if admin_token and token != admin_token:
        return jsonify({ 'ok': False, 'error': 'forbidden' }), 403
    return jsonify({ 'ok': True, 'pins': PIN_MAP })
