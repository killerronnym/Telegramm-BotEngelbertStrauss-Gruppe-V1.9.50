import os
import sys
from sqlalchemy import create_engine, text

# Add parent dir to path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from shared_bot_utils import get_db_url

def list_tables():
    url = get_db_url()
    print(f"Connecting to: {url}")
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES")).fetchall()
        print("\nTables in database:")
        for r in result:
            print(f"- {r[0]}")

if __name__ == "__main__":
    list_tables()
