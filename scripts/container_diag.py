
import os
import sys
# Path setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from shared_bot_utils import get_db_url, get_bot_config
from sqlalchemy import create_engine, text

def run_diag():
    url = get_db_url()
    # Mask password for security
    masked_url = url
    if "@" in url:
        parts = url.split("@")
        pre = parts[0].split(":")
        if len(pre) > 2:
            masked_url = f"{pre[0]}:{pre[1]}:****@{parts[1]}"
            
    print(f"Resolved DB URL: {masked_url}")
    
    # Try connecting
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            print("Database connection SUCCESSFUL.")
            res = conn.execute(text("SELECT bot_name, is_active FROM bot_settings")).fetchall()
            print(f"Found {len(res)} bot settings.")
            for r in res:
                print(f" - {r[0]}: active={r[1]}")
    except Exception as e:
        print(f"Database connection FAILED: {e}")

    # Check Specific Configs
    for b in ['quiz', 'umfrage']:
        cfg = get_bot_config(b)
        print(f"\nConfig for {b}:")
        if not cfg:
            print(" EMPTY (or error)")
        else:
            # Mask sensitive parts
            if "bot_token" in cfg:
                t = cfg["bot_token"]
                cfg["bot_token"] = f"{t[:5]}...{t[-5:]}" if len(t) > 10 else "SET"
            import json
            print(json.dumps(cfg, indent=2))

if __name__ == "__main__":
    run_diag()
