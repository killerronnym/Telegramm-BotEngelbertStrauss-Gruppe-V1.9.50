
import os
import json
from sqlalchemy import create_engine, text
from datetime import datetime

# Remote MySQL URL from .env
DB_URL = "mysql+pymysql://Drago:Ronny22092020%40@rinno.myds.me:3306/TelecombotDrago?charset=utf8mb4"

def run_diag():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        print(f"--- UTC Time: {datetime.utcnow()} ---")
        
        print("\n--- RECENT AUDIT LOGS ---")
        logs = conn.execute(text("SELECT id, action, details, timestamp FROM audit_log ORDER BY timestamp DESC LIMIT 5")).fetchall()
        for l in logs:
            print(f"ID: {l[0]} | Action: {l[1]} | Time: {l[3]} | Details: {l[2]}")
            
    # Check Files
    root = "c:/Users/Ronny M PC/Documents/Bot T"
    q_tmp = os.path.join(root, "bots", "quiz_bot", "send_now.tmp")
    u_tmp = os.path.join(root, "bots", "umfrage_bot", "send_now.tmp")
    
    print("\n--- TRIGGER FILES ---")
    for name, path in [("Quiz", q_tmp), ("Umfrage", u_tmp)]:
        exists = os.path.exists(path)
        print(f"{name} Trigger ({path}): {'EXISTS' if exists else 'not found'}")
        if exists:
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            print(f"  Modified: {mtime}")

if __name__ == "__main__":
    run_diag()
