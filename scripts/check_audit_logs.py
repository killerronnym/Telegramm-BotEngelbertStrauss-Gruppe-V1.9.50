
import os
import json
from sqlalchemy import create_engine, text

# Remote MySQL URL from .env
DB_URL = "mysql+pymysql://Drago:Ronny22092020%40@rinno.myds.me:3306/TelecombotDrago?charset=utf8mb4"

def run_diag():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        print("--- RECENT AUDIT LOGS (Last 20) ---")
        logs = conn.execute(text("SELECT id, user_id, action, timestamp FROM audit_log ORDER BY timestamp DESC LIMIT 20")).fetchall()
        for l in logs:
            print(f"ID: {l[0]} | User: {l[1]} | Action: {l[2]} | Time: {l[3]}")
            
        print("\n--- BOT SETTINGS (Quiz & Umfrage) ---")
        settings = conn.execute(text("SELECT bot_name, is_active FROM bot_settings WHERE bot_name IN ('quiz', 'umfrage')")).fetchall()
        for s in settings:
            print(f"Bot: {s[0]} | Active: {s[1]}")

if __name__ == "__main__":
    run_diag()
