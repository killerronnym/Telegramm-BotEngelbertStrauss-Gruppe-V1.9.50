
import os
import sys
import json
from sqlalchemy import create_engine, text

# Pfade bestimmen
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from shared_bot_utils import get_db_url

def check_system():
    db_url = get_db_url()
    print(f"Checking DB: {db_url.split('@')[-1] if '@' in db_url else db_url}")
    engine = create_engine(db_url)
    
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT config_json FROM bot_settings WHERE bot_name='system'")
            ).fetchone()
            
            if result:
                config = json.loads(result[0])
                print(f"System Config: {json.dumps(config, indent=2)}")
            else:
                print("No config found for 'system'")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_system()
