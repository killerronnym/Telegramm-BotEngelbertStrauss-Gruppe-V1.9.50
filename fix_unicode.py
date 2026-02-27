import sys
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)

from web_dashboard.app.models import db, BotSettings
from shared_bot_utils import get_shared_flask_app

app = get_shared_flask_app()

def fix_config():
    with app.app_context():
        s = BotSettings.query.filter_by(bot_name='invite').first()
        if not s:
            print("Settings not found.")
            return

        try:
            # Let's try to parse it, and if it fails, fallback to a clean list
            cfg = json.loads(s.config_json)
            print("Config parsed successfully. Dumping back with ensure_ascii=True to be safe.")
            s.config_json = json.dumps(cfg, ensure_ascii=True)
            db.session.commit()
            print("Fixed successfully.")
        except Exception as e:
            print(f"Failed to parse json. It might be permanently corrupted. Resetting form_fields array. Error: {e}")
            
            # Find the bad part or just reset form fields. Usually the corruption is in form_fields.
            # We'll just load default fields so the bot can start.
            default_fields = [
                {'id': 'name', 'emoji': '👤', 'display_name': 'Alias', 'label': 'Wie lautet dein Alias / Spitzname?', 'type': 'text', 'required': True, 'enabled': True},
                {'id': 'age', 'emoji': '🎂', 'display_name': 'Alter', 'label': 'Wie alt bist du?', 'type': 'number', 'required': True, 'enabled': True, 'min_age': 16, 'min_age_error_msg': 'Dein Alter reicht leider noch nicht für diese Gruppe.'}
            ]
            cfg = json.loads(s.config_json.encode('utf-8', 'replace').decode('utf-8', 'ignore')) # attempt aggressive recovery if possible
            
            # Actually, standard fallback: 
            cfg = {'is_enabled': False, 'bot_token': '', 'main_chat_id': '', 'topic_id': '', 'link_ttl_minutes': 15, 'start_message': 'Willkommen!', 'rules_message': 'Bitte beachte die Regeln.', 'blocked_message': 'Du bist gesperrt.', 'privacy_policy': 'Datenschutz...', 'whitelist_enabled': False, 'whitelist_approval_chat_id': '', 'whitelist_approval_topic_id': '', 'whitelist_pending_message': 'Wird geprüft.', 'whitelist_rejection_message': 'Abgelehnt.'}
            cfg['form_fields'] = default_fields
            
            s.config_json = json.dumps(cfg, ensure_ascii=True)
            s.is_active = False
            db.session.commit()
            print("Reset the invite bot config completely to safe defaults because of fatal corruption.")

if __name__ == '__main__':
    fix_config()
