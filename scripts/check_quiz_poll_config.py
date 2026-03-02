import json
import sys
from sqlalchemy import create_engine, text

# Versuche shared_bot_utils zu importieren
try:
    from shared_bot_utils import get_db_url
except ImportError:
    import sys
    import os
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from shared_bot_utils import get_db_url

def run_diag():
    db_url = get_db_url()
    if not db_url:
        print("Fehler: Datenbank-URL konnte nicht ermittelt werden (.env prüfen).")
        sys.exit(1)
        
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            for bot in ['quiz', 'umfrage']:
                print(f"\n--- {bot.upper()} BOT SETTINGS ---")
                settings = conn.execute(text(f"SELECT bot_name, is_active, config_json FROM bot_settings WHERE bot_name='{bot}'")).fetchone()
                if settings:
                    print(f"Aktiv (Dashboard): {settings[1]}")
                    config = json.loads(settings[2]) if settings[2] else {}
                    # Token maskieren
                    token = config.get('bot_token', '')
                    masked_token = (token[:10] + "...") if len(token) > 10 else token
                    print(f"Token: {masked_token}")
                    print(f"Channel ID: {config.get('channel_id') or config.get('channel_id_quiz') or config.get('channel_id_umfrage')}")
                    print(f"Topic ID: {config.get('topic_id')}")
                else:
                    print(f"{bot.upper()} Einstellungen NICHT GEFUNDEN")
    except Exception as e:
        print(f"Fehler bei der Datenbankverbindung: {e}")

if __name__ == "__main__":
    run_diag()
