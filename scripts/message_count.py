
import os
import sys
import json
from sqlalchemy import create_engine, text
from datetime import datetime

# Set output to UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Remote MySQL URL
DB_URL = "mysql+pymysql://Drago:Ronny22092020%40@rinno.myds.me:3306/TelecombotDrago?charset=utf8mb4"

def check_messages():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        print("--- LAST 10 MESSAGES IN DB ---")
        try:
            rows = conn.execute(text("SELECT id, telegram_user_id, text, timestamp, chat_type, chat_id FROM id_finder_message ORDER BY timestamp DESC LIMIT 10")).fetchall()
            if not rows:
                print("No messages found in id_finder_message.")
            for r in rows:
                print(f"ID: {r[0]} | User: {r[1]} | Type: {r[4]} | Chat: {r[5]} | Text: {str(r[2])[:20]!r} | Time: {r[3]}")
            
            count = conn.execute(text("SELECT COUNT(*) FROM id_finder_message")).scalar()
            print(f"\nTotal messages: {count}")
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    check_messages()
