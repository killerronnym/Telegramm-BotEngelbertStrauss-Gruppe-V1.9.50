
import os
import json
from sqlalchemy import create_engine, inspect

# Remote MySQL URL from .env
DB_URL = "mysql+pymysql://Drago:Ronny22092020%40@rinno.myds.me:3306/TelecombotDrago?charset=utf8mb4"

def run_diag():
    engine = create_engine(DB_URL)
    inspector = inspect(engine)
    print("--- TABLES ---")
    tables = inspector.get_table_names()
    for t in tables:
        print(t)
        
    if "audit_log" in tables:
         with engine.connect() as conn:
              count = conn.execute(text("SELECT COUNT(*) FROM audit_log")).scalar()
              print(f"\nAudit Log Count: {count}")

if __name__ == "__main__":
    from sqlalchemy import text # Fix missing import
    run_diag()
