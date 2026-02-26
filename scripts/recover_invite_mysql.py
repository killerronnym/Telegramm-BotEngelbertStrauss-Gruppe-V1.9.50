
import os
import sys
import json
import traceback

# Pfade bestimmen
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from shared_bot_utils import get_db_url
from sqlalchemy import create_engine, text

CONFIG_PATH = os.path.join(PROJECT_ROOT, 'bots', 'invite_bot', 'invite_bot_config.json')

def recover():
    print("--- Start MySQL Recovery ---")
    
    if not os.path.exists(CONFIG_PATH):
        print(f"Fehler: {CONFIG_PATH} nicht gefunden.")
        return

    db_url = get_db_url()
    print(f"Verwende DB-URL (gekürzt): {db_url.split('@')[-1] if '@' in db_url else db_url}")

    print(f"Lese alte Konfiguration aus {CONFIG_PATH}...")
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    config_json = json.dumps(config)

    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            # Prüfen ob Eintrag existiert
            result = conn.execute(
                text("SELECT id FROM bot_settings WHERE bot_name = 'invite'")
            ).fetchone()

            if result:
                print("Eintrag für 'invite' gefunden. Aktualisiere MySQL...")
                conn.execute(
                    text("UPDATE bot_settings SET config_json = :config, is_active = 1 WHERE bot_name = 'invite'"),
                    {"config": config_json}
                )
            else:
                print("Kein Eintrag für 'invite' gefunden. Erstelle neu in MySQL...")
                conn.execute(
                    text("INSERT INTO bot_settings (bot_name, config_json, is_active) VALUES ('invite', :config, 1)"),
                    {"config": config_json}
                )
            
            conn.commit()
            print("SUCCESS: Die Konfiguration wurde erfolgreich in die MySQL-Datenbank übertragen!")
            print("Bitte lade das Dashboard jetzt neu.")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    recover()
