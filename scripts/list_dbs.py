
import os
import json
from sqlalchemy import create_engine, text

# Remote MySQL URL (no DB name)
BASE_URL = "mysql+pymysql://Drago:Ronny22092020%40@rinno.myds.me:3306/?charset=utf8mb4"

def run_diag():
    engine = create_engine(BASE_URL)
    with engine.connect() as conn:
        print("--- DATABASES ---")
        dbs = conn.execute(text("SHOW DATABASES")).fetchall()
        for d in dbs:
            print(d[0])

if __name__ == "__main__":
    run_diag()
