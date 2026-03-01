import os
import sys
from sqlalchemy import create_engine, text

# Add parent dir to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from shared_bot_utils import get_db_url

def check_messages():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    url = get_db_url()
    print(f"Connecting to: {url}")
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM id_finder_message ORDER BY timestamp DESC LIMIT 30")).fetchall()
        print("\nRecent messages (Last 30):")
        for r in result:
            text_val = r.text if r.text else "[No Text]"
            print(f" - [{r.timestamp}] Chat: {r.chat_id}, User: {r.telegram_user_id}, Topic: {r.message_thread_id}, Text: {text_val}")

if __name__ == "__main__":
    check_messages()
