import os
import sys
import json
from datetime import datetime
from sqlalchemy import create_engine, text

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from shared_bot_utils import get_db_url

def check():
    url = get_db_url()
    print(f"Connecting to: {url}")
    engine = create_engine(url)
    today = datetime.now()
    print(f"Server Time: {today.strftime('%Y-%m-%d %H:%M:%S')}")
    
    with engine.connect() as conn:
        # Settings
        s = conn.execute(text("SELECT config_json FROM bot_settings WHERE bot_name = 'birthday'")).fetchone()
        if s:
            cfg = json.loads(s[0])
            print(f"Announce Time in DB: {cfg.get('announce_time')}")
            print(f"Target Chat ID: {cfg.get('target_chat_id')}")
            print(f"Target Topic ID: {cfg.get('target_topic_id')}")
        else:
            print("No birthday settings found.")
            
        # Birthdays Today
        res = conn.execute(text("SELECT * FROM birthday WHERE day = :d AND month = :m"), 
                         {'d': today.day, 'm': today.month}).fetchall()
        print(f"Birthdays for {today.day}.{today.month}. Found: {len(res)}")
        for r in res:
            print(f" - User ID: {r.telegram_user_id}, Name: {r.first_name}, Username: {r.username}")

if __name__ == "__main__":
    check()
