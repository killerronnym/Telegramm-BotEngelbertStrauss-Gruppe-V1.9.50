import os
import sys

# Add project root to path for imports
sys.path.append(os.getcwd())

from web_dashboard.app import create_app
from web_dashboard.app.models import db, IDFinderUser

app = create_app()
with app.app_context():
    users = IDFinderUser.query.all()
    print(f"Total Users: {len(users)}")
    for u in users:
        print(f"UID={u.telegram_id} | Name={u.first_name} | Contact={u.first_contact}")
