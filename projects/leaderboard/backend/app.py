import pathlib
import os
from flask import Flask, send_from_directory

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / 'frontend'
BUILD_DIR = FRONTEND_DIR / 'client' / 'build'
STATIC_DIR = BUILD_DIR / 'static'

from blueprints.picks import picks_bp
from blueprints.auth import auth_bp
from blueprints.leaderboard import leaderboard_bp
from blueprints.api import api_bp

app = Flask(__name__, static_folder=str(STATIC_DIR))

app.register_blueprint(picks_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(leaderboard_bp)
app.register_blueprint(api_bp)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(os.path.join(BUILD_DIR, path)):
        return send_from_directory(BUILD_DIR, path)
    else:
        return send_from_directory(BUILD_DIR, 'index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8000'))
    app.run(host='0.0.0.0', port=port)
