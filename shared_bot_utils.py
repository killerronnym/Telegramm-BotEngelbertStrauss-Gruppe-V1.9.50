import os
import sys
import json
from sqlalchemy import create_engine, text, inspect

# Pfade bestimmen
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DASHBOARD_DIR = os.path.join(PROJECT_ROOT, 'web_dashboard')
# Correctly point to the instance directory in the project root
INSTANCE_DIR = os.path.join(PROJECT_ROOT, 'instance')
DB_PATH = os.path.join(INSTANCE_DIR, 'app.db')
from dotenv import load_dotenv

# dotenv laden um .env Variablen wie DATABASE_URL verfügbar zu machen
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

def get_db_url():
    """Gibt die konfigurierte Datenbank-URL zurück oder fällt auf SQLite zurück."""
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        return db_url
    
    # Fallback SQLite
    INSTANCE_DIR = os.path.join(PROJECT_ROOT, 'instance')
    if not os.path.exists(INSTANCE_DIR):
        os.makedirs(INSTANCE_DIR)
    return f"sqlite:///{os.path.join(INSTANCE_DIR, 'app.db')}"

# The web_dashboard already creates the `bot_settings` table via SQLAlchemy Models.
# We don't need to manually create the table here anymore, we can just assume it exists
# if the main app has started and the migration plan executed.

def get_bot_config(bot_name):
    """
    Lädt die Konfiguration für einen Bot aus der Datenbank.
    Gibt ein leeres Dictionary zurück, falls keine Config existiert.
    """
    try:
        engine = create_engine(get_db_url())
        with engine.connect() as conn:
            result = conn.execute(

                text("SELECT config_json FROM bot_settings WHERE bot_name = :name"),
                {"name": bot_name}
            ).fetchone()
            
            if result and result[0]:
                # print(f"DEBUG: Config found for {bot_name}.")
                return json.loads(result[0])
            else:
                # print(f"DEBUG: No config found for {bot_name}. Returning empty dict.")
                return {}
    except Exception as e:
        print(f"FEHLER: Beim Laden der Config für {bot_name}: {e}")
        return {}

def get_env_var(key, default=None):
    """
    Lädt eine Umgebungsvariable (z.B. aus .env).
    """
    return os.environ.get(key, default)
