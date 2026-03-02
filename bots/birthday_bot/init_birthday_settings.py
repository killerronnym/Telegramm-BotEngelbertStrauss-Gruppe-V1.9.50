import os
import sys
import json
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from shared_bot_utils import get_shared_flask_app
from web_dashboard.app.models import BotSettings, db

def init_birthday():
    flask_app = get_shared_flask_app()
    with flask_app.app_context():
        s = BotSettings.query.filter_by(bot_name='birthday').first()
        if not s:
            cfg = {
                'registration_text': 'Dein Geburtstag ({day}.{month}.) wurde erfolgreich eingetragen!',
                'congratulation_text': 'Herzlichen Glückwunsch zum Geburtstag, {user}!',
                'prompt_text': '🎂 <b>Geburtstags-Bot</b>\n\nWann hast du Geburtstag?\nBitte schreibe es im Format <code>Tag.Monat</code> oder <code>Tag.Monat.Jahr</code>.\n<i>(Beispiel: 15.08. oder 15.08.1990 - das Jahr ist komplett freiwillig!)</i>\n\nWenn du abbrechen möchtest, tippe /cancel.',
                'error_format_text': 'Das war leider das falsche Format.\nBeispiele: `15.08.` oder `15 08 1990`\nVersuche es nochmal oder tippe /cancel.',
                'error_date_text': 'Das ist leider kein echtes Kalenderdatum. Bitte versuche es noch einmal:',
                'cancel_text': 'Geburtstags-Eintragung abgebrochen.',
                'announce_time': '00:01',
                'target_chat_id': '',
                'target_topic_id': '',
                'is_active': True
            }
            s = BotSettings(
                bot_name='birthday', 
                config_json=json.dumps(cfg),
                is_active=True
            )
            db.session.add(s)
            db.session.commit()
            print("Birthday settings initialized in DB.")
        else:
            print("Birthday settings already exist.")
            # Ensure it is active
            s.is_active = True
            db.session.commit()
            print("Birthday bot set to active.")

if __name__ == "__main__":
    init_birthday()
