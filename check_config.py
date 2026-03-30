import json
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from web_dashboard.app import create_app
from web_dashboard.app.models import db, BotSettings

app = create_app()
with app.app_context():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    if s:
        cfg = json.loads(s.config_json)
        print(json.dumps(cfg, indent=4))
    else:
        print("Invite Bot settings not found.")
