import os
import sqlite3

def explore_db(path):
    try:
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        if 'group_event' in tables:
            cursor.execute("SELECT COUNT(*) FROM group_event")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"FOUND DATA IN: {path} ({count} events)")
                cursor.execute("SELECT id, title FROM group_event")
                for r in cursor.fetchall():
                    print(f"  - [{r[0]}] {r[1]}")
    except:
        pass

print("Searching for databases with active event data...")
for root, dirs, files in os.walk('.'):
    for file in files:
        if file.endswith('.db') or '.' not in file: # Check even files without extensions if they are large
            full_path = os.path.join(root, file)
            if os.path.getsize(full_path) > 1024:
                explore_db(full_path)
