import os
import sys
import json
from sqlalchemy import create_engine, text

# Pfade bestimmen
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'app.db')

# Direkte DB-Verbindung für Bots (ohne kompletten Flask-Overhead)
def get_bot_config(bot_name):
    """
    Lädt die Konfiguration für einen Bot aus der SQLite-Datenbank.
    Gibt ein leeres Dictionary zurück, falls keine Config existiert.
    """
    if not os.path.exists(DB_PATH):
        print(f"Warnung: Datenbank nicht gefunden unter {DB_PATH}")
        return {}
    
    try:
        # Verbindung zur SQLite DB
        engine = create_engine(f'sqlite:///{DB_PATH}')
        with engine.connect() as conn:
            # Query ausführen
            result = conn.execute(
                text("SELECT config_json FROM bot_settings WHERE bot_name = :name"),
                {"name": bot_name}
            ).fetchone()
            
            if result and result[0]:
                return json.loads(result[0])
            else:
                return {}
    except Exception as e:
        print(f"Fehler beim Laden der Config für {bot_name}: {e}")
        return {}

def get_env_var(key, default=None):
    """
    Lädt eine Umgebungsvariable (z.B. aus .env).
    """
    return os.environ.get(key, default)
