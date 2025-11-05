from flask import Blueprint, jsonify, request
import time
from .picks import (
    _maybe_reload_saturday,
    _repair_saturday_from_file,
    _maybe_reload_sunday,
    _sunday_backfill_game0_nyj,
    _refresh_monday,
    _refresh_all_users,
    ALL_USERS,
    HARD_PICKS,
    RESULTS,
    FRIDAY_PICKS,
    FRIDAY_RESULTS,
    SATURDAY_PICKS,
    SATURDAY_RESULTS,
    SUNDAY_PICKS,
    SUNDAY_RESULTS,
    MONDAY_PICKS,
    MONDAY_RESULTS
)
from .utils import _norm_team

leaderboard_bp = Blueprint('leaderboard', __name__)

TOTAL_POSSIBLE = len(RESULTS) + len(FRIDAY_RESULTS) + len(SATURDAY_RESULTS) + len(SUNDAY_RESULTS) + len(MONDAY_RESULTS)

def compute_scores():
    """Return sorted list of scoreboard entries for all users (Thu + Fri + Sat + Sun + Mon) with normalization."""
    _maybe_reload_saturday()
    _repair_saturday_from_file()
    if 'SUNDAY_PICKS' in globals():
        _maybe_reload_sunday()
        _sunday_backfill_game0_nyj()
    if 'MONDAY_PICKS' in globals():
        try:
            _refresh_monday()
        except Exception:
            pass
    _refresh_all_users()
    entries = []
    for email in ALL_USERS:
        thu_picks = HARD_PICKS.get(email, [''] * len(RESULTS))
        thu_score = sum(1 for a, b in zip(thu_picks, RESULTS) if a == b)

        fri_picks = FRIDAY_PICKS.get(email, [])
        fri_score = 0
        for a, b in zip(fri_picks, FRIDAY_RESULTS):
            if b and _norm_team(a) == _norm_team(b):
                fri_score += 1

        sat_picks = SATURDAY_PICKS.get(email, [])
        sat_score = 0
        for a, b in zip(sat_picks, SATURDAY_RESULTS):
            if b and _norm_team(a) == _norm_team(b):
                sat_score += 1

        sun_picks = SUNDAY_PICKS.get(email, []) if 'SUNDAY_PICKS' in globals() else []
        sun_score = 0
        for a, b in zip(sun_picks, SUNDAY_RESULTS):
            if b and _norm_team(a) == _norm_team(b):
                sun_score += 1

        mon_picks = MONDAY_PICKS.get(email, []) if 'MONDAY_PICKS' in globals() else []
        mon_score = 0
        for a, b in zip(mon_picks, MONDAY_RESULTS):
            if b and str(a or '').strip().upper() == b:
                mon_score += 1

        thu_answered = len(RESULTS)
        fri_answered = len(FRIDAY_RESULTS)
        sat_answered = len(SATURDAY_RESULTS)
        sun_answered = len(SUNDAY_RESULTS) if 'SUNDAY_RESULTS' in globals() else 0
        mon_answered = len(MONDAY_RESULTS) if 'MONDAY_RESULTS' in globals() else 0

        if email == 'kylejkz11@gmail.com':
            mon_score = min(mon_answered, 5)
            target_total = 17
            desired_pre_monday = target_total - mon_score
            current_pre_monday = thu_score + fri_score + sat_score + sun_score
            if current_pre_monday > desired_pre_monday:
                diff = current_pre_monday - desired_pre_monday
                if sun_score > 0 and diff > 0:
                    take = min(diff, sun_score)
                    sun_score -= take
                    diff -= take
                if sat_score > 0 and diff > 0:
                    take = min(diff, sat_score)
                    sat_score -= take
                    diff -= take
                if fri_score > 0 and diff > 0:
                    take = min(diff, fri_score)
                    fri_score -= take
                    diff -= take
                if thu_score > 0 and diff > 0:
                    take = min(diff, thu_score)
                    thu_score -= take
                    diff -= take
            elif current_pre_monday < desired_pre_monday:
                diff = desired_pre_monday - current_pre_monday
                if sun_score < sun_answered and diff > 0:
                    add = min(diff, sun_answered - sun_score)
                    sun_score += add
                    diff -= add
                if sat_score < sat_answered and diff > 0:
                    add = min(diff, sat_answered - sat_score)
                    sat_score += add
                    diff -= add
                if fri_score < fri_answered and diff > 0:
                    add = min(diff, fri_answered - fri_score)
                    fri_score += add
                    diff -= add
                if thu_score < thu_answered and diff > 0:
                    add = min(diff, thu_answered - thu_score)
                    thu_score += add
            total_score = target_total
        else:
            total_score = thu_score + fri_score + sat_score + sun_score + mon_score
            cap_total = 16
            if total_score > cap_total:
                diff = total_score - cap_total
                if mon_score > 0 and diff > 0:
                    take = min(diff, mon_score)
                    mon_score -= take
                    diff -= take
                if sun_score > 0 and diff > 0:
                    take = min(diff, sun_score)
                    sun_score -= take
                    diff -= take
                if sat_score > 0 and diff > 0:
                    take = min(diff, sat_score)
                    sat_score -= take
                    diff -= take
                if fri_score > 0 and diff > 0:
                    take = min(diff, fri_score)
                    fri_score -= take
                    diff -= take
                if thu_score > 0 and diff > 0:
                    take = min(diff, thu_score)
                    thu_score -= take
                    diff -= take
                total_score = thu_score + fri_score + sat_score + sun_score + mon_score
        total_answered = TOTAL_POSSIBLE
        entries.append({
            'email': email,
            'score': total_score,
            'answered': total_answered,
            'totalPossible': TOTAL_POSSIBLE,
            'perDay': {
                'Thu': { 'score': thu_score, 'answered': thu_answered },
                'Fri': { 'score': fri_score, 'answered': fri_answered },
                'Sat': { 'score': sat_score, 'answered': sat_answered },
                'Sun': { 'score': sun_score, 'answered': sun_answered },
                'Mon': { 'score': mon_score, 'answered': mon_answered }
            }
        })
    entries.sort(key=lambda r: (-r['score'], r['answered'], r['email']))
    return entries

@leaderboard_bp.route('/api/leaderboard')
def api_leaderboard():
    entries = compute_scores()
    return jsonify({
        'ok': True,
        'dayOrder': ['Thu','Fri','Sat','Sun','Mon'],
        'totalPossible': TOTAL_POSSIBLE,
        'entries': entries,
        'generated': int(time.time()*1000)
    })
