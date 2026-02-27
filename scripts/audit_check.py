
import os
import json
from sqlalchemy import create_engine, text
from datetime import datetime

# Remote MySQL URL from .env
DB_URL = "mysql+pymysql://Drago:Ronny22092020%40@rinno.myds.me:3306/TelecombotDrago?charset=utf8mb4"

def run_diag():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        print(f"--- SCRIPT START ---")
        print(f"Current Local Time: {datetime.now()}")
        
        # Check Audit Log
        print("\n--- AUDIT LOGS (LAST 20) ---")
        try:
            logs = conn.execute(text("SELECT id, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 20")).fetchall()
            if not logs:
                print("No audit logs found.")
            for l in logs:
                print(f"ID: {l[0]} | Action: {l[1]} | Time: {l[3]} | Details: {l[2]}")
        except Exception as e:
            print(f"Error querying audit_log: {e}")
            
        # Check last 5 broadcasts too
        print("\n--- BROADCASTS (LAST 5) ---")
        try:
            bc = conn.execute(text("SELECT id, status, scheduled_at, text FROM broadcast ORDER BY id DESC LIMIT 5")).fetchall()
            for b in bc:
                print(f"ID: {b[0]} | Status: {b[1]} | Scheduled: {b[2]} | Text: {b[3][:30]}...")
        except Exception as e:
             print(f"Error querying broadcast: {e}")

if __name__ == "__main__":
    run_diag()
