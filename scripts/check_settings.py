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
            print("--- BOT SETTINGS CHECK ---")
            rows = conn.execute(text("SELECT bot_name, is_active, config_json FROM bot_settings")).fetchall()
            for r in rows:
                name, active, cfg_json = r
                print(f"\nBot: {name} | Aktiv: {active}")
                if cfg_json:
                    try:
                        cfg = json.loads(cfg_json)
                        # Token maskieren für Sicherheit
                        if "bot_token" in cfg:
                            token = cfg["bot_token"]
                            cfg["bot_token"] = f"{token[:5]}...{token[-5:]}" if len(token) > 10 else "SET"
                        print(f"Konfiguration: {json.dumps(cfg, indent=2)}")
                    except:
                        print(f"Konfiguration (Raw): {cfg_json}")
                else:
                    print("Konfiguration: KEINE")
    except Exception as e:
        print(f"Fehler bei der Datenbankverbindung: {e}")

if __name__ == "__main__":
    run_diag()
