import os
import json
import sys
from datetime import datetime

# Add project root to path for imports
sys.path.append(os.getcwd())

from web_dashboard.app import create_app
from web_dashboard.app.models import db, IDFinderMessage, IDFinderUser, InviteLog
from sqlalchemy import func, extract

app = create_app()
with app.app_context():
    print("\n--- SAMPLE DATA CHECK ---")
    msg = IDFinderMessage.query.first()
    if msg:
        print(f"Message ID: {msg.id} | Timestamp: {msg.timestamp} ({type(msg.timestamp)})")
        try:
            db.session.query(extract('year', IDFinderMessage.timestamp)).first()
            print("SQLite extract('year') works.")
        except Exception as e:
            print(f"SQLite extract('year') FAILED: {e}")
            
        try:
            db.session.query(func.date(IDFinderMessage.timestamp)).first()
            print("SQLite func.date() works.")
        except Exception as e:
            print(f"SQLite func.date() FAILED: {e}")
            
    else:
        print("No messages found.")
        
    log = InviteLog.query.first()
    if log:
        print(f"Log ID: {log.id} | Timestamp: {log.timestamp} ({type(log.timestamp)})")
    else:
        print("No invite logs found.")

    print("\n--- TESTING ANALYTICS QUERIES ---")
    try:
        total_messages = IDFinderMessage.query.count()
        print(f"Total messages count works: {total_messages}")
    except Exception as e:
        print(f"Count FAILED: {e}")
