import os
import sys
from datetime import datetime, timedelta

# Add project root to path for imports
sys.path.append(os.getcwd())

from web_dashboard.app import create_app
from web_dashboard.app.models import IDFinderMessage
from sqlalchemy import func

app = create_app()
with app.app_context():
    def fmt_dt(d):
        if not d: return ""
        if isinstance(d, str):
            if len(d) == 10 and d[4] == '-' and d[7] == '-': # YYYY-MM-DD
                return f"{d[8:10]}.{d[5:7]}"
            return d
        return d.strftime('%d.%m')

    days = 7
    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)
    
    date_expr = func.date(IDFinderMessage.timestamp)
    timeline_query = db.session.query(
        date_expr.label('date'),
        func.count(IDFinderMessage.id).label('count')
    ).filter(IDFinderMessage.timestamp >= cutoff).group_by(date_expr).all()
    
    date_map = {fmt_dt(row.date): row.count for row in timeline_query if row.date}
    print(f"Date Map: {date_map}")
    
    timeline_labels = []
    total_data = []
    for i in range(days-1, -1, -1):
        d = now - timedelta(days=i)
        d_str = d.strftime('%d.%m')
        timeline_labels.append(d_str)
        total_data.append(date_map.get(d_str, 0))
        
    print(f"Labels: {timeline_labels}")
    print(f"Data: {total_data}")
