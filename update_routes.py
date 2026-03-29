new_code = r'''
import os
from flask import send_file, redirect, jsonify, request, render_template

AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'static', 'avatars')
os.makedirs(AVATAR_DIR, exist_ok=True)

@bp.route('/api/avatar/<int:user_id>')
def get_avatar(user_id):
    avatar_path = os.path.join(AVATAR_DIR, f"{user_id}.jpg")
    if os.path.exists(avatar_path):
        response = send_file(avatar_path, mimetype='image/jpeg')
        response.headers['Cache-Control'] = 'public, max-age=604800'
        return response

    from ..models import IDFinderUser
    user = IDFinderUser.query.filter_by(telegram_id=user_id).first()

    if user and user.photo_url:
        return redirect(f"https://ui-avatars.com/api/?name={user.first_name or 'U'}&background=random&color=fff&size=128")

    name = (user.first_name[0] if user.first_name else 'U') if user else 'U'
    return redirect(f"https://ui-avatars.com/api/?name={name}&background=1d4ed8&color=fff&size=128&bold=true")

@bp.route('/id-finder/analytics')
@login_required
def id_finder_analytics():
    sys.stdout.write("--- [DEBUG] Entered new id_finder_analytics ---\n")
    sys.stdout.flush()
    try:
        from ..models import IDFinderMessage, IDFinderUser, IDFinderAdmin, InviteLog
        
        PALETTE=['#4f8ef7','#a855f7','#ec4899','#22c55e','#f59e0b','#ef4444','#14b8a6','#8b5cf6','#f97316','#06b6d4']
        
        days = int(request.args.get('days') or 30)
        month = int(request.args.get('month') or 0)
        year = int(request.args.get('year') or 0)

        now = datetime.utcnow()
        cutoff = now - timedelta(days=days)

        if year > 0 and month > 0:
            query_filter = (extract('year', IDFinderMessage.timestamp) == year) & (extract('month', IDFinderMessage.timestamp) == month)
            cutoff = datetime(year, month, 1)
        elif year > 0:
            query_filter = extract('year', IDFinderMessage.timestamp) == year
            cutoff = datetime(year, 1, 1)
        else:
            query_filter = IDFinderMessage.timestamp >= cutoff

        total_users = IDFinderUser.query.count()
        total_messages = IDFinderMessage.query.filter(query_filter).count()
        total_media = IDFinderMessage.query.filter(query_filter, IDFinderMessage.content_type != 'text').count()
        
        active_users_sq = db.session.query(IDFinderMessage.telegram_user_id).filter(query_filter).distinct().subquery()
        active_users = db.session.query(func.count(active_users_sq.c.telegram_user_id)).scalar()

        leaderboard_raw = []
        if total_messages > 0:
            leaderboard_raw = db.session.query(
                IDFinderUser.telegram_id,
                IDFinderUser.first_name,
                IDFinderUser.username,
                IDFinderUser.photo_url,
                IDFinderUser.created_at if hasattr(IDFinderUser, 'created_at') else getattr(IDFinderUser, 'first_contact', None),
                func.count(IDFinderMessage.id).label('msg_count'),
                func.sum(case((IDFinderMessage.content_type != 'text', 1), else_=0)).label('media_count')
            ).join(IDFinderMessage, IDFinderUser.telegram_id == IDFinderMessage.telegram_user_id) \
             .filter(query_filter) \
             .group_by(IDFinderUser.telegram_id, IDFinderUser.first_name,
                       IDFinderUser.username, IDFinderUser.photo_url,
                       IDFinderUser.created_at if hasattr(IDFinderUser, 'created_at') else getattr(IDFinderUser, 'first_contact', None)) \
             .order_by(text('msg_count DESC')).limit(10).all()

        admins = {str(a.telegram_id) for a in IDFinderAdmin.query.all()}
        leaderboard = []
        for i, row in enumerate(leaderboard_raw):
            c_date = row[4]
            leaderboard.append({
                "uid": str(row.telegram_id),
                "name": row.first_name or "Unbekannt",
                "username": f"@{row.username}" if row.username else "—",
                "avatar_url": f"/api/avatar/{row.telegram_id}",
                "msgs": int(row.msg_count),
                "media": int(row.media_count or 0),
                "joined_at": c_date.strftime('%d.%m.%Y') if c_date and hasattr(c_date, 'strftime') else "—",
                "rank": i + 1,
                "status": "admin" if str(row.telegram_id) in admins else "member",
            })

        if total_messages == 0 and total_users > 0:
            recent_users = IDFinderUser.query.order_by(IDFinderUser.last_contact.desc()).limit(10).all()
            for i, u in enumerate(recent_users):
                c_date = getattr(u, 'created_at', getattr(u, 'first_contact', None))
                leaderboard.append({
                    "uid": str(u.telegram_id), "name": u.first_name or "Unbekannt", "username": f"@{u.username}" if u.username else "—",
                    "avatar_url": f"/api/avatar/{u.telegram_id}", "msgs": 0, "media": 0, "joined_at": c_date.strftime('%d.%m.%Y') if c_date and hasattr(c_date, 'strftime') else "—",
                    "rank": i + 1, "status": "admin" if str(u.telegram_id) in admins else "member"
                })

        timeline_query = db.session.query(func.date(IDFinderMessage.timestamp).label('date'), func.count(IDFinderMessage.id).label('count')).filter(query_filter).group_by('date').order_by('date').all()
        def fmt_dt(d):
            if not d: return ""
            try: return d.strftime('%d.%m') if hasattr(d, 'strftime') else d if isinstance(d, str) and '.' in d else f"{str(d).split('-')[2][:2]}.{str(d).split('-')[1]}"
            except: return str(d)

        date_map = {fmt_dt(row.date): row.count for row in timeline_query if row.date}
        timeline_labels, total_data = [], []
        for i in range(days - 1, -1, -1):
            d = now - timedelta(days=i)
            d_str = d.strftime('%d.%m')
            timeline_labels.append(d_str)
            total_data.append(date_map.get(d_str, 0))

        hours_query = db.session.query(extract('hour', IDFinderMessage.timestamp).label('hour'), func.count(IDFinderMessage.id).label('count')).filter(query_filter).group_by('hour').all()
        busiest_hours = [0] * 24
        for row in hours_query:
            if row.hour is not None: busiest_hours[int(row.hour)] = int(row.count)

        engine_name = db.engine.dialect.name
        dow_expr = func.dayofweek(IDFinderMessage.timestamp) if engine_name == 'mysql' else extract('dow', IDFinderMessage.timestamp)
        dow_query = db.session.query(dow_expr.label('dow'), func.count(IDFinderMessage.id).label('count')).filter(query_filter).group_by('dow').all()
        busiest_days = [0] * 7
        for row in dow_query:
            if row.dow is not None:
                py_dow = (int(row.dow) + 5) % 7 if engine_name == 'mysql' else (int(row.dow) + 6) % 7
                busiest_days[py_dow] = int(row.count)

        type_query = db.session.query(IDFinderMessage.content_type, func.count(IDFinderMessage.id).label('count')).filter(query_filter).group_by(IDFinderMessage.content_type).all()
        msg_types_dict = {row.content_type: int(row.count) for row in type_query}
        msg_types = [{"type": k.capitalize() if k else "Unbekannt", "val": v, "color": PALETTE[i%10]} for i, (k,v) in enumerate(msg_types_dict.items())]

        heatmap_query = db.session.query(dow_expr.label('dow'), extract('hour', IDFinderMessage.timestamp).label('hour'), func.count(IDFinderMessage.id).label('count')).filter(query_filter).group_by('dow', 'hour').all()
        heatmap_matrix = [[0] * 24 for _ in range(7)]
        for row in heatmap_query:
            if row.dow is not None and row.hour is not None:
                py_dow = (int(row.dow) + 5) % 7 if engine_name == 'mysql' else (int(row.dow) + 6) % 7
                heatmap_matrix[py_dow][int(row.hour)] = int(row.count)

        growth_query = db.session.query(
            func.date(InviteLog.timestamp).label('date'),
            func.sum(case((InviteLog.action.ilike('%beigetreten%'), 1), else_=0)).label('joins'),
            func.sum(case((InviteLog.action.ilike('%verlassen%') | InviteLog.action.ilike('%entfernt%'), 1), else_=0)).label('leaves')
        ).filter(InviteLog.timestamp >= cutoff).group_by('date').order_by('date').all()

        growth_labels, growth_net = [], []
        g_joins = {fmt_dt(r.date): int(r.joins) for r in growth_query if r.date}
        g_leaves = {fmt_dt(r.date): int(r.leaves) for r in growth_query if r.date}
        for i in range(days - 1, -1, -1):
            d = now - timedelta(days=i)
            d_str = d.strftime('%d.%m')
            growth_labels.append(d_str)
            growth_net.append(g_joins.get(d_str, 0) - g_leaves.get(d_str, 0))

        joins_leaves = InviteLog.query.filter(InviteLog.action.ilike('%beigetreten%') | InviteLog.action.ilike('%verlassen%') | InviteLog.action.ilike('%entfernt%')).order_by(InviteLog.timestamp.desc()).limit(30).all()
        events_list = [{"time": e.timestamp.strftime('%d.%m %H:%M') if hasattr(e.timestamp, 'strftime') else str(e.timestamp), "user": e.username or f"id{e.telegram_user_id}", "uid": str(e.telegram_user_id), "type": "join" if "beigetreten" in str(e.action) else "leave"} for e in joins_leaves]

        return render_template('id_finder_analytics.html',
            stats={'total_users': total_users, 'total_messages': total_messages, 'total_media': total_media, 'active_users': active_users, 'avg_per_day': round(total_messages / max(days, 1), 1)},
            activity={'timeline': {'labels': timeline_labels, 'total': total_data}, 'leaderboard': leaderboard, 'busiest_hours': busiest_hours, 'busiest_days': busiest_days, 'msg_types': msg_types, 'heatmap': heatmap_matrix, 'growth': {'labels': growth_labels, 'net': growth_net}, 'events': events_list},
            filter_days=days, filter_month=month, filter_year=year)
    except Exception as e:
        import traceback; sys.stderr.write(f"ERROR: {e}\n{traceback.format_exc()}\n")
        return f"Fehler: {e}", 500

@bp.route('/api/id-finder/user-detail/<int:uid>')
@login_required
def id_finder_user_detail_api(uid):
    try:
        from ..models import IDFinderUser, IDFinderMessage, TopicMapping, IDFinderAdmin, BotSettings
        user = IDFinderUser.query.filter_by(telegram_id=uid).first_or_404()
        total_msgs = IDFinderMessage.query.filter_by(telegram_user_id=uid).count()
        total_media = IDFinderMessage.query.filter(IDFinderMessage.telegram_user_id==uid, IDFinderMessage.content_type != 'text').count()
        active_days = db.session.query(func.count(func.distinct(func.date(IDFinderMessage.timestamp)))).filter_by(telegram_user_id=uid).scalar() or 0

        subq = db.session.query(IDFinderMessage.telegram_user_id, func.count(IDFinderMessage.id).label('cnt')).group_by(IDFinderMessage.telegram_user_id).subquery()
        rank_result = db.session.query(func.count()).filter(subq.c.cnt > db.session.query(subq.c.cnt).filter(subq.c.telegram_user_id == uid).scalar_subquery()).scalar()
        rank = (rank_result or 0) + 1

        now = datetime.utcnow()
        cutoff_14 = now - timedelta(days=14)
        tl_query = db.session.query(func.date(IDFinderMessage.timestamp).label('date'), func.count(IDFinderMessage.id).label('count')).filter(IDFinderMessage.telegram_user_id == uid, IDFinderMessage.timestamp >= cutoff_14).group_by('date').order_by('date').all()
        tl_map = {r.date.strftime('%d.%m') if hasattr(r.date, 'strftime') else str(r.date)[:10].split('-')[2]+'.'+str(r.date)[:10].split('-')[1]: r.count for r in tl_query if r.date}
        timeline_labels, timeline_data = [], []
        for i in range(13, -1, -1):
            lbl = (now - timedelta(days=i)).strftime('%d.%m')
            timeline_labels.append(lbl); timeline_data.append(tl_map.get(lbl, 0))

        types_query = db.session.query(IDFinderMessage.content_type, func.count(IDFinderMessage.id).label('count')).filter_by(telegram_user_id=uid).group_by(IDFinderMessage.content_type).all()
        msg_types = {r.content_type: int(r.count) for r in types_query}

        topic_query = db.session.query(IDFinderMessage.message_thread_id, func.count(IDFinderMessage.id).label('count')).filter(IDFinderMessage.telegram_user_id == uid, IDFinderMessage.message_thread_id != None).group_by(IDFinderMessage.message_thread_id).order_by(text('count DESC')).limit(5).all()
        topic_map = {t.topic_id: t.topic_name for t in TopicMapping.query.all()}
        topics = [{"name": topic_map.get(str(r.message_thread_id), f"Topic {r.message_thread_id}"), "count": int(r.count)} for r in topic_query]

        recent = IDFinderMessage.query.filter_by(telegram_user_id=uid).order_by(IDFinderMessage.timestamp.desc()).limit(5).all()
        recent_msgs = [{"time": m.timestamp.strftime('%d.%m. %H:%M') if hasattr(m.timestamp, 'strftime') else '—', "type": m.content_type or 'text', "preview": getattr(m, 'text_preview', None) or f"[{m.content_type}]"} for m in recent]

        is_admin = IDFinderAdmin.query.filter_by(telegram_id=uid).first() is not None
        c_date = getattr(user, 'created_at', getattr(user, 'first_contact', None))

        return jsonify({
            "uid": str(uid), "name": user.first_name or "Unbekannt", "username": f"@{user.username}" if user.username else "—",
            "language": user.language_code or "—", "status": "admin" if is_admin else "member", "avatar_url": f"/api/avatar/{uid}",
            "total_msgs": total_msgs, "total_media": total_media, "active_days": active_days,
            "joined_at": c_date.strftime('%d.%m.%Y') if c_date and hasattr(c_date, 'strftime') else "—",
            "last_active": user.last_contact.strftime('%d.%m. %H:%M') if user.last_contact and hasattr(user.last_contact, 'strftime') else "—",
            "avg_per_day": round(total_msgs / max(active_days, 1), 1),
            "rank": rank, "warnings": 0, "timeline_14d": timeline_data, "timeline_labels": timeline_labels,
            "msg_types": msg_types, "topics": topics, "recent_messages": recent_msgs
        })
    except Exception as e:
        import traceback; sys.stderr.write(f"API Error {e}\n{traceback.format_exc()}\n"); return jsonify({'error': str(e)}), 500
'''

import re

with open('web_dashboard/app/routes/dashboard.py', 'r', encoding='utf-8') as f:
    content = f.read()

start_idx = content.find("@bp.route('/id-finder/analytics')")
if start_idx == -1:
    start_idx = content.find('@bp.route("/id-finder/analytics")')

end_idx = content.find("@bp.route('/id-finder/profiles')")
if end_idx == -1:
    end_idx = content.find('@bp.route("/id-finder/profiles")')

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_code + "\n\n" + content[end_idx:]
    with open('web_dashboard/app/routes/dashboard.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Dashboard Python API setup installed correctly.")
else:
    print(f"FAILED indexing. start_idx={start_idx}, end_idx={end_idx}")
