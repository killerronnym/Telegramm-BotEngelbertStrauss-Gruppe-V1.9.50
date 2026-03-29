import os
import json
import sys

# Add project root to path for imports
sys.path.append(os.getcwd())

from web_dashboard.app import create_app
from web_dashboard.app.models import BotSettings, IDFinderUser

app = create_app()
with app.app_context():
    print("--- BOT SETTINGS CHECK ---")
    settings = BotSettings.query.all()
    for s in settings:
        try:
            cfg = json.loads(s.config_json)
            has_token = "bot_token" in cfg and len(cfg["bot_token"]) > 10
            print(f"Bot: {s.bot_name:20} | Active: {s.is_active} | Token exists: {has_token}")
        except:
            print(f"Bot: {s.bot_name:20} | ERROR PARSING JSON")
            
    print("\n--- DATABASE COUNTS ---")
    try:
        user_count = IDFinderUser.query.count()
        print(f"IDFinder Users: {user_count}")
    except Exception as e:
        print(f"Error counting users: {e}")
