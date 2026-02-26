
import os
import json
import sqlite3

# Absolute Pfade für Windows
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTANCE_DIR = os.path.join(PROJECT_ROOT, 'instance')
DB_PATH = os.path.join(INSTANCE_DIR, 'app.db')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'bots', 'invite_bot', 'invite_bot_config.json')

def recover():
    if not os.path.exists(CONFIG_PATH):
        print(f"Fehler: {CONFIG_PATH} nicht gefunden.")
        return

    if not os.path.exists(DB_PATH):
        print(f"Fehler: Datenbank {DB_PATH} nicht gefunden.")
        return

    print(f"Lese alte Konfiguration aus {CONFIG_PATH}...")
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    config_json = json.dumps(config)

    print(f"Verbinde mit Datenbank {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Prüfen ob Eintrag existiert
        cursor.execute("SELECT id FROM bot_settings WHERE bot_name = 'invite'")
        row = cursor.fetchone()

        if row:
            print("Eintrag für 'invite' gefunden. Aktualisiere...")
            cursor.execute(
                "UPDATE bot_settings SET config_json = ?, is_active = 1 WHERE bot_name = 'invite'",
                (config_json,)
            )
        else:
            print("Kein Eintrag für 'invite' gefunden. Erstelle neu...")
            cursor.execute(
                "INSERT INTO bot_settings (bot_name, config_json, is_active) VALUES (?, ?, ?)",
                ('invite', config_json, 1)
            )
        
        conn.commit()
        print("Success: Configuration restored!")
    except Exception as e:
        print(f"Error during recovery: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    recover()
