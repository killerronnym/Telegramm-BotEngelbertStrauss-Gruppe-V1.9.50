import os
import sys
import json
from sqlalchemy import create_engine, text

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from shared_bot_utils import get_db_url

def check_birthday():
    url = get_db_url()
    print(f"Connecting to: {url}")
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT bot_name, config_json, is_active FROM bot_settings WHERE bot_name = 'birthday'")).fetchone()
        if result:
            print(f"Bot: {result[0]}")
            print(f"Is Active (Column): {result[2]}")
            try:
                config = json.loads(result[1])
                print(f"Is Active (JSON): {config.get('is_active')}")
                print(f"Full Config: {result[1]}")
            except:
                print("Could not parse JSON config")
        else:
            print("No settings found for 'birthday'")

if __name__ == "__main__":
    check_birthday()
