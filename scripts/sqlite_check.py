
import os
import sqlite3
from datetime import datetime

# Local SQLite DB
DB_PATH = "c:/Users/Ronny M PC/Documents/Bot T/instance/app.db"

def run_diag():
    if not os.path.exists(DB_PATH):
        print(f"File {DB_PATH} not found.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("--- TABLES (SQLite) ---")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [t[0] for t in cursor.fetchall()]
    for t in tables:
        print(t)
        
    if "audit_log" in tables:
        cursor.execute("SELECT id, action, details, timestamp FROM audit_log ORDER BY id DESC LIMIT 10")
        logs = cursor.fetchall()
        print(f"\nAudit Log Count: {len(logs)}")
        for l in logs:
            print(f"ID: {l[0]} | Action: {l[1]} | Time: {l[3]} | Details: {l[2]}")
    else:
        print("\nTable audit_log not found in SQLite.")
        
    conn.close()

if __name__ == "__main__":
    run_diag()
