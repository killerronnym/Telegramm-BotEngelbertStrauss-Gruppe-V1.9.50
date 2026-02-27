
import os
import json
from sqlalchemy import create_engine, text

# Remote MySQL URL from .env
DB_URL = "mysql+pymysql://Drago:Ronny22092020%40@rinno.myds.me:3306/TelecombotDrago?charset=utf8mb4"

def run_diag():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        print("--- BOT SETTINGS CHECK ---")
        rows = conn.execute(text("SELECT bot_name, is_active, config_json FROM bot_settings")).fetchall()
        for r in rows:
            name, active, cfg_json = r
            print(f"\nBot: {name} | Active: {active}")
            if cfg_json:
                try:
                    cfg = json.loads(cfg_json)
                    # Mask token
                    if "bot_token" in cfg:
                        token = cfg["bot_token"]
                        cfg["bot_token"] = f"{token[:5]}...{token[-5:]}" if len(token) > 10 else "SET"
                    print(f"Config: {json.dumps(cfg, indent=2)}")
                except:
                    print(f"Config (Raw): {cfg_json}")
            else:
                print("Config: NONE")

if __name__ == "__main__":
    run_diag()
