import os
import sys
import traceback
from datetime import datetime, timedelta

# Add project root to path for imports
sys.path.append(os.getcwd())

from web_dashboard.app import create_app
from web_dashboard.app.models import db, IDFinderUser, IDFinderMessage, InviteLog, TopicMapping
from sqlalchemy import func, case

app = create_app()
with app.app_context():
    test_uid = 453315338
    print(f"--- Diagnosing User {test_uid} ---")
    try:
        user = IDFinderUser.query.filter_by(telegram_id=test_uid).first()
        if not user:
            print("User not found in IDFinderUser table.")
        else:
            print(f"User Name: {user.first_name}")
            print(f"First Contact: {user.first_contact} (Type: {type(user.first_contact)})")
            
            # Test Stats
            msgs = IDFinderMessage.query.filter_by(telegram_user_id=test_uid).count()
            print(f"Messages: {msgs}")
            
            # Test Ranking
            rank_query = db.session.query(IDFinderMessage.telegram_user_id, func.count(IDFinderMessage.id).label('c')).group_by(IDFinderMessage.telegram_user_id).order_by(db.text('c DESC')).all()
            rank = next((i + 1 for i, r in enumerate(rank_query) if r.telegram_user_id == test_uid), 0)
            print(f"Rank: {rank}")
            
    except Exception as e:
        print(f"CRASH in User Details test: {e}")
        traceback.print_exc()

    print("\n--- Diagnosing Growth Query ---")
    try:
        cutoff = datetime.utcnow() - timedelta(days=7)
        growth_query = db.session.query(
            func.date(InviteLog.timestamp).label('date'),
            func.sum(case((InviteLog.action.ilike('%beigetreten%'), 1), else_=0)).label('joins'),
            func.sum(case((InviteLog.action.ilike('%verlassen%') | InviteLog.action.ilike('%entfernt%'), 1), else_=0)).label('leaves')
        ).filter(InviteLog.timestamp >= cutoff) \
         .group_by(func.date(InviteLog.timestamp)).all()
        
        print(f"Growth Result Rows: {len(growth_query)}")
        for row in growth_query:
            print(f"Date={row.date} | Joins={row.joins} | Leaves={row.leaves}")
            
    except Exception as e:
        print(f"CRASH in Growth test: {e}")
        traceback.print_exc()

    print("\n--- Checking InviteLog Actions ---")
    actions = db.session.query(InviteLog.action, func.count(InviteLog.id)).group_by(InviteLog.action).all()
    for action, count in actions:
        print(f"Action: '{action}' | Count: {count}")
