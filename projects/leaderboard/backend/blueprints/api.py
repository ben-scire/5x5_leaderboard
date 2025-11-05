from flask import Blueprint, jsonify
import requests

api_bp = Blueprint('api', __name__)

BASE_URL = 'https://site.web.api.espn.com/apis/site/v2/sports'

@api_bp.route('/api/espn/game/<sport>/<league>/<game_id>')
def get_game_data(sport, league, game_id):
    url = f'{BASE_URL}/{sport}/{league}/summary?event={game_id}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
