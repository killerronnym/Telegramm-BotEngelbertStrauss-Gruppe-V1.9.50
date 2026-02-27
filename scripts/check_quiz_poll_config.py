
import os
import json
from sqlalchemy import create_engine, text

# Remote MySQL URL from .env
DB_URL = "mysql+pymysql://Drago:Ronny22092020%40@rinno.myds.me:3306/TelecombotDrago?charset=utf8mb4"

def run_diag():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        for bot in ['quiz', 'umfrage']:
            print(f"\n--- {bot.upper()} BOT SETTINGS ---")
            settings = conn.execute(text(f"SELECT bot_name, is_active, config_json FROM bot_settings WHERE bot_name='{bot}'")).fetchone()
            if settings:
                print(f"Active (Dashboard): {settings[1]}")
                config = json.loads(settings[2]) if settings[2] else {}
                # Token maskieren
                token = config.get('bot_token', '')
                masked_token = (token[:10] + "...") if len(token) > 10 else token
                print(f"Token: {masked_token}")
                print(f"Channel ID: {config.get('channel_id') or config.get('channel_id_quiz') or config.get('channel_id_umfrage')}")
                print(f"Topic ID: {config.get('topic_id')}")
            else:
                print(f"{bot.upper()} settings NOT FOUND")

if __name__ == "__main__":
    run_diag()
