from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
import os
import json
import subprocess
import sys
import signal
from datetime import datetime, timedelta
from sqlalchemy import func
from werkzeug.utils import secure_filename
from ..models import db, BotSettings, Broadcast, TopicMapping, User, IDFinderAdmin, IDFinderUser, IDFinderMessage

# Wir definieren den Blueprint explizit
bp = Blueprint('dashboard', __name__)

# Pfade berechnen
CURRENT_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_FILE_DIR, '../../..'))
BASE_DIR = os.path.join(PROJECT_ROOT, 'web_dashboard')

# Bot PID Files
INVITE_BOT_PID_FILE = os.path.join(BASE_DIR, "invite_bot.pid")
ID_FINDER_BOT_PID_FILE = os.path.join(BASE_DIR, "id_finder_bot.pid")
TIKTOK_BOT_PID_FILE = os.path.join(BASE_DIR, "tiktok_bot.pid")

# Log Files
INVITE_BOT_ERROR_LOG = os.path.join(BASE_DIR, "invite_bot_error.log")
USER_INTERACTION_LOG_FILE = os.path.join(PROJECT_ROOT, "user_interactions.log")
INVITE_BOT_LOG_FILE = os.path.join(BASE_DIR, "invite_bot.log")
ID_FINDER_BOT_LOG_FILE = os.path.join(PROJECT_ROOT, "bots", "id_finder_bot", "id_finder_bot.log")
TIKTOK_BOT_LOG_FILE = os.path.join(PROJECT_ROOT, "bots", "tiktok_bot", "tiktok_bot.log")

def is_process_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def get_bot_status_simple():
    status = {
        "invite": {"running": False}, "quiz": {"running": False}, 
        "umfrage": {"running": False}, "outfit": {"running": False}, 
        "id_finder": {"running": False}, "tiktok": {"running": False}
    }
    def check_pid(key, path):
        if os.path.exists(path):
            try:
                with open(path, 'r') as f: pid = int(f.read().strip())
                if is_process_running(pid): status[key]["running"] = True
                else: os.remove(path)
            except: 
                if os.path.exists(path): os.remove(path)
    check_pid("invite", INVITE_BOT_PID_FILE)
    check_pid("id_finder", ID_FINDER_BOT_PID_FILE)
    check_pid("tiktok", TIKTOK_BOT_PID_FILE)
    return status

@bp.context_processor
def inject_globals():
    return {"bot_status": get_bot_status_simple()}

@bp.route('/')
@bp.route('/dashboard')
def index():
    version_path = os.path.join(PROJECT_ROOT, 'version.json')
    version = {"version": "1.0.0"}
    if os.path.exists(version_path):
        try:
            with open(version_path, 'r') as f: version = json.load(f)
        except: pass
    layout_settings = BotSettings.query.filter_by(bot_name='dashboard_layout').first()
    layout = json.loads(layout_settings.config_json) if layout_settings else None
    return render_template('index.html', version=version, layout=layout)

@bp.route('/api/dashboard/save-layout', methods=['POST'])
def save_dashboard_layout():
    data = request.json
    s = BotSettings.query.filter_by(bot_name='dashboard_layout').first()
    if not s: s = BotSettings(bot_name='dashboard_layout', config_json=json.dumps(data)); db.session.add(s)
    else: s.config_json = json.dumps(data)
    db.session.commit()
    return jsonify({"success": True})

# --- INVITE BOT ROUTES ---
@bp.route('/bot-settings', methods=["GET", "POST"])
def bot_settings():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    if not s:
        cfg = {'is_enabled': False, 'bot_token': '', 'main_chat_id': '', 'topic_id': '', 'link_ttl_minutes': 15, 'start_message': 'Willkommen!', 'rules_message': 'Bitte beachte die Regeln.', 'blocked_message': 'Du bist gesperrt.', 'privacy_policy': 'Datenschutz...', 'form_fields': [], 'whitelist_enabled': False, 'whitelist_approval_chat_id': '', 'whitelist_approval_topic_id': '', 'whitelist_pending_message': 'Wird geprüft.', 'whitelist_rejection_message': 'Abgelehnt.'}
        s = BotSettings(bot_name='invite', config_json=json.dumps(cfg)); db.session.add(s); db.session.commit()
    
    if request.method == 'POST':
        action = request.form.get('action')
        config = json.loads(s.config_json)
        if action == 'save_base_config':
            config.update({'is_enabled': 'is_enabled' in request.form, 'bot_token': request.form.get('bot_token', ''), 'main_chat_id': request.form.get('main_chat_id', ''), 'topic_id': request.form.get('topic_id', ''), 'link_ttl_minutes': request.form.get('link_ttl_minutes', 15, type=int), 'whitelist_enabled': 'whitelist_enabled' in request.form, 'whitelist_approval_chat_id': request.form.get('whitelist_approval_chat_id', ''), 'whitelist_approval_topic_id': request.form.get('whitelist_approval_topic_id', '')})
            s.config_json = json.dumps(config); db.session.commit(); flash('Gespeichert.', 'success')
        return redirect(url_for('dashboard.bot_settings'))

    logs = []
    if os.path.exists(INVITE_BOT_LOG_FILE):
        with open(INVITE_BOT_LOG_FILE, 'r') as f: logs = f.readlines()[-50:]
    return render_template("bot_settings.html", config=json.loads(s.config_json), is_invite_running=get_bot_status_simple()['invite']['running'], user_interaction_logs=[], invite_bot_logs=logs)

@bp.route('/bot-settings/save-content', methods=['POST'])
def save_invite_content():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json)
    cfg.update({k: request.form.get(k, '') for k in ['start_message', 'rules_message', 'blocked_message', 'privacy_policy', 'whitelist_pending_message', 'whitelist_rejection_message']})
    s.config_json = json.dumps(cfg); db.session.commit(); flash('Texte gespeichert.', 'success')
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/add-field', methods=['POST'])
def add_field():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json); fields = cfg.setdefault('form_fields', [])
    fields.append({'id': request.form.get('field_id'), 'emoji': request.form.get('emoji', '🔹'), 'display_name': request.form.get('display_name', ''), 'label': request.form.get('label', ''), 'type': request.form.get('type', 'text'), 'required': 'required' in request.form, 'enabled': True})
    s.config_json = json.dumps(cfg); db.session.commit(); return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/edit-field', methods=['POST'])
def edit_field():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json); fid = request.form.get('field_id')
    for f in cfg.get('form_fields', []):
        if f['id'] == fid: f.update({'emoji': request.form.get('emoji'), 'display_name': request.form.get('display_name'), 'label': request.form.get('label'), 'type': request.form.get('type'), 'required': 'required' in request.form, 'enabled': 'enabled' in request.form})
    s.config_json = json.dumps(cfg); db.session.commit(); return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/delete-field', methods=['POST'])
def delete_field():
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json); fid = request.form.get('field_id')
    cfg['form_fields'] = [f for f in cfg.get('form_fields', []) if f['id'] != fid]
    s.config_json = json.dumps(cfg); db.session.commit(); return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/move-field/<string:field_id>/<string:direction>', methods=['POST'])
def invite_bot_move_field(field_id, direction):
    s = BotSettings.query.filter_by(bot_name='invite').first()
    cfg = json.loads(s.config_json); fs = cfg.get('form_fields', [])
    idx = next((i for i, f in enumerate(fs) if f['id'] == field_id), -1)
    if idx != -1:
        if direction == 'up' and idx > 0: fs[idx], fs[idx-1] = fs[idx-1], fs[idx]
        elif direction == 'down' and idx < len(fs)-1: fs[idx], fs[idx+1] = fs[idx+1], fs[idx]
    s.config_json = json.dumps(cfg); db.session.commit(); return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/clear-logs/user', methods=['POST'])
def clear_user_logs():
    if os.path.exists(USER_INTERACTION_LOG_FILE): open(USER_INTERACTION_LOG_FILE, 'w').close()
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/bot-settings/clear-logs/system', methods=['POST'])
def clear_system_logs():
    if os.path.exists(INVITE_BOT_LOG_FILE): open(INVITE_BOT_LOG_FILE, 'w').close()
    return redirect(url_for('dashboard.bot_settings'))

# --- BROADCAST ROUTES ---
@bp.route('/broadcast_manager')
def broadcast_manager():
    ts = TopicMapping.query.all(); bs = Broadcast.query.order_by(Broadcast.created_at.desc()).all()
    return render_template('broadcast_manager.html', known_topics={str(t.topic_id): t.topic_name for t in ts}, broadcasts=bs)

@bp.route('/broadcast_manager/save', methods=['POST'])
def save_broadcast():
    m = request.files.get('media'); mpath, mtype = None, None
    if m and m.filename:
        fname = secure_filename(m.filename); fdir = os.path.join(BASE_DIR, 'app', 'static', 'uploads'); os.makedirs(fdir, exist_ok=True)
        m.save(os.path.join(fdir, fname)); mpath = f'uploads/{fname}'
        mtype = 'image' if fname.lower().endswith(('.png', '.jpg', '.jpeg')) else 'video'
    b = Broadcast(text=request.form.get('text'), topic_id=request.form.get('topic_id'), scheduled_at=datetime.utcnow(), media_path=mpath, media_type=mtype)
    db.session.add(b); db.session.commit(); flash('Eingestellt.', 'success'); return redirect(url_for('dashboard.broadcast_manager'))

@bp.route('/broadcast_manager/topic/save', methods=['POST'])
def save_topic_mapping():
    tid, tname = request.form.get('topic_id'), request.form.get('topic_name')
    m = TopicMapping.query.filter_by(topic_id=tid).first()
    if m: m.topic_name = tname
    else: db.session.add(TopicMapping(topic_id=tid, topic_name=tname))
    db.session.commit(); return redirect(url_for('dashboard.broadcast_manager'))

@bp.route('/broadcast_manager/topic/delete/<topic_id>', methods=['POST'])
def delete_topic_mapping(topic_id):
    m = TopicMapping.query.filter_by(topic_id=topic_id).first()
    if m: db.session.delete(m); db.session.commit()
    return redirect(url_for('dashboard.broadcast_manager'))

@bp.route('/broadcast_manager/delete/<int:broadcast_id>', methods=['POST'])
def delete_broadcast(broadcast_id):
    b = Broadcast.query.get(broadcast_id)
    if b: db.session.delete(b); db.session.commit()
    return redirect(url_for('dashboard.broadcast_manager'))

# --- OTHER BOT ROUTES ---
@bp.route('/live-moderation')
def live_moderation(): return render_template('live_moderation.html')

@bp.route('/quiz-settings', methods=['GET', 'POST'])
def quiz_settings():
    s = BotSettings.query.filter_by(bot_name='quiz').first()
    if not s: s = BotSettings(bot_name='quiz', config_json='{}'); db.session.add(s); db.session.commit()
    return render_template('quiz_settings.html', schedule={}, stats={'total': 0, 'asked': 0, 'remaining': 0}, config=json.loads(s.config_json), questions_json='[]', asked_questions_json='[]', logs=[])

@bp.route('/umfrage-settings', methods=['GET', 'POST'])
def umfrage_settings():
    s = BotSettings.query.filter_by(bot_name='umfrage').first()
    if not s: s = BotSettings(bot_name='umfrage', config_json='{}'); db.session.add(s); db.session.commit()
    return render_template('umfrage_settings.html', config=json.loads(s.config_json), schedule={}, stats={}, logs=[])

@bp.route('/outfit-bot', methods=['GET', 'POST'])
def outfit_bot_dashboard():
    s = BotSettings.query.filter_by(bot_name='outfit').first()
    if not s: s = BotSettings(bot_name='outfit', config_json='{}'); db.session.add(s); db.session.commit()
    return render_template('outfit_bot_dashboard.html', config=json.loads(s.config_json), is_running=get_bot_status_simple()['outfit']['running'], logs=[], duel_status={'active': False})

@bp.route('/outfit-bot/actions/<action>', methods=['POST'])
def outfit_bot_actions(action):
    # Dummy Action Handler
    flash(f"Aktion {action} ausgeführt.", "info")
    return redirect(url_for('dashboard.outfit_bot_dashboard'))

@bp.route('/critical-errors')
def critical_errors():
    logs = []
    lpath = os.path.join(BASE_DIR, "critical_errors.log")
    if os.path.exists(lpath):
        with open(lpath, 'r') as f: logs = f.readlines()
    return render_template("critical_errors.html", critical_logs=logs)

@bp.route('/critical-errors/clear', methods=['POST'])
def clear_critical_errors():
    lpath = os.path.join(BASE_DIR, "critical_errors.log")
    if os.path.exists(lpath): open(lpath, 'w').close()
    return redirect(url_for('dashboard.critical_errors'))

@bp.route('/id-finder')
def id_finder_dashboard():
    s = BotSettings.query.filter_by(bot_name='id_finder').first()
    if not s:
        cfg = {'bot_token': '', 'admin_group_id': 0, 'main_group_id': 0}
        s = BotSettings(bot_name='id_finder', config_json=json.dumps(cfg))
        db.session.add(s)
        db.session.commit()
    
    cfg = json.loads(s.config_json)
    us = IDFinderUser.query.order_by(IDFinderUser.last_contact.desc()).all()
    return render_template('id_finder_dashboard.html', config=cfg, user_registry=us, is_running=get_bot_status_simple()['id_finder']['running'], logs=[])

@bp.route('/id-finder/save-config', methods=['POST'])
def id_finder_save_config():
    s = BotSettings.query.filter_by(bot_name='id_finder').first()
    cfg = json.loads(s.config_json)
    cfg.update({
        'bot_token': request.form.get('bot_token', ''),
        'admin_group_id': request.form.get('admin_group_id', ''),
        'main_group_id': request.form.get('main_group_id', ''),
        'admin_log_topic_id': request.form.get('admin_log_topic_id', ''),
        'delete_commands': 'delete_commands' in request.form,
        'bot_message_cleanup_seconds': int(request.form.get('bot_message_cleanup_seconds') or 0),
        'message_logging_enabled': 'message_logging_enabled' in request.form,
        'message_logging_ignore_commands': 'message_logging_ignore_commands' in request.form,
        'message_logging_groups_only': 'message_logging_groups_only' in request.form,
        'max_warnings': int(request.form.get('max_warnings') or 3),
        'punishment_type': request.form.get('punishment_type', 'none'),
        'mute_duration': int(request.form.get('mute_duration') or 24),
        'cleanup_notification_seconds': int(request.form.get('cleanup_notification_seconds') or 60),
        'warning_bot_name': request.form.get('warning_bot_name', 'id_finder')
    })
    s.config_json = json.dumps(cfg)
    db.session.commit()
    flash('Einstellungen gespeichert.', 'success')
    return redirect(url_for('dashboard.id_finder_dashboard'))

@bp.route('/id-finder/user/<int:user_id>')
def id_finder_user_detail(user_id):
    u = IDFinderUser.query.filter_by(telegram_id=user_id).first_or_404()
    ms = IDFinderMessage.query.filter_by(telegram_user_id=user_id).order_by(IDFinderMessage.timestamp.desc()).limit(100).all()
    return render_template('id_finder_user_detail.html', user=u, messages=ms)

@bp.route('/id-finder/delete-user/<int:user_id>', methods=['POST'])
def id_finder_delete_user(user_id):
    u = IDFinderUser.query.filter_by(telegram_id=user_id).first()
    if u: db.session.delete(u); db.session.commit()
    return redirect(url_for('dashboard.id_finder_dashboard'))

@bp.route('/id-finder/commands')
def id_finder_commands(): return render_template('id_finder_commands.html')

@bp.route('/id-finder/admin-panel')
def id_finder_admin_panel():
    ads = IDFinderAdmin.query.all()
    # Mocking admins as a dictionary for the template for demo purposes if needed, 
    # but the template expects a dict per the loop: `for admin_id, admin_data in admins.items()`
    # We should convert ads list to dict:
    admins_dict = {str(a.telegram_user_id): {'name': a.name, 'permissions': json.loads(a.permissions) if a.permissions else {}} for a in ads}
    return render_template('id_finder_admin_panel.html', admins=admins_dict, available_permission_groups={}, available_permissions={})

@bp.route('/id-finder/admin-panel/add', methods=['POST'])
def id_finder_add_admin():
    admin_id = request.form.get('admin_id')
    admin_name = request.form.get('admin_name')
    if admin_id and admin_name:
        existing = IDFinderAdmin.query.filter_by(telegram_user_id=int(admin_id)).first()
        if not existing:
            new_admin = IDFinderAdmin(telegram_user_id=int(admin_id), name=admin_name, permissions='{}')
            db.session.add(new_admin)
            db.session.commit()
            flash('Admin erfolgreich hinzugefügt.', 'success')
        else:
            flash('Admin existiert bereits.', 'warning')
    return redirect(url_for('dashboard.id_finder_admin_panel'))

@bp.route('/id-finder/admin-panel/delete', methods=['POST'])
def id_finder_delete_admin():
    admin_id = request.form.get('admin_id')
    if admin_id:
        admin = IDFinderAdmin.query.filter_by(telegram_user_id=int(admin_id)).first()
        if admin:
            db.session.delete(admin)
            db.session.commit()
            flash('Admin erfolgreich gelöscht.', 'success')
    return redirect(url_for('dashboard.id_finder_admin_panel'))

@bp.route('/id-finder/admin-panel/update-permissions', methods=['POST'])
def id_finder_update_admin_permissions():
    admin_id = request.form.get('admin_id')
    if admin_id:
        admin = IDFinderAdmin.query.filter_by(telegram_user_id=int(admin_id)).first()
        if admin:
            # All form fields except admin_id are considered permissions
            perms = {k: True for k in request.form.keys() if k != 'admin_id'}
            admin.permissions = json.dumps(perms)
            db.session.commit()
            flash('Berechtigungen erfolgreich aktualisiert.', 'success')
    return redirect(url_for('dashboard.id_finder_admin_panel'))

@bp.route('/id-finder/analytics')
def id_finder_analytics():
    try:
        days = int(request.args.get('days') or 7)
    except ValueError:
        days = 7

    try:
        month = int(request.args.get('month') or 0)
        year = int(request.args.get('year') or 0)
    except ValueError:
        month = 0
        year = 0

    query_filter = True
    base_query = IDFinderMessage.query
    
    # Handle time filtering
    now = datetime.utcnow()
    if year > 0 and month > 0:
        query_filter = (db.extract('year', IDFinderMessage.timestamp) == year) & (db.extract('month', IDFinderMessage.timestamp) == month)
    elif year > 0:
        query_filter = db.extract('year', IDFinderMessage.timestamp) == year
    elif days > 0:
        cutoff = now - timedelta(days=days)
        query_filter = IDFinderMessage.timestamp >= cutoff

    total_users = IDFinderUser.query.count()

    # Leaderboard
    leaderboard_query = db.session.query(
        IDFinderUser.telegram_id,
        IDFinderUser.first_name,
        func.count(IDFinderMessage.id).label('msg_count'),
        func.sum(db.case((IDFinderMessage.content_type != 'text', 1), else_=0)).label('media_count')
    ).join(IDFinderMessage, IDFinderUser.telegram_id == IDFinderMessage.telegram_user_id) \
     .filter(query_filter) \
     .group_by(IDFinderUser.telegram_id, IDFinderUser.first_name) \
     .order_by(db.text('msg_count DESC')).limit(100).all()

    leaderboard = [
        {"uid": str(row.telegram_id), "name": row.first_name or "Unknown", "msgs": int(row.msg_count), "media": int(row.media_count or 0)}
        for row in leaderboard_query
    ]

    # Timeline (Messages per day)
    timeline_query = db.session.query(
        func.date(IDFinderMessage.timestamp).label('date'),
        func.count(IDFinderMessage.id).label('count')
    ).filter(query_filter).group_by('date').order_by('date').all()

    # Make sure timeline has continuous dates for the requested period if filtering by days
    timeline_labels = []
    total_data = []
    
    if days > 0 and year == 0 and month == 0:
        date_map = {row.date.strftime('%d.%m'): row.count for row in timeline_query if row.date}
        for i in range(days-1, -1, -1):
            d = now - timedelta(days=i)
            d_str = d.strftime('%d.%m')
            timeline_labels.append(d_str)
            total_data.append(date_map.get(d_str, 0))
    else:
        # For month/year filtering, rely on the data returned directly
        timeline_labels = [row.date.strftime('%d.%m') if row.date else 'Unknown' for row in timeline_query]
        total_data = [row.count for row in timeline_query]

    # Hours distribution
    # Using generic cast since extract('hour') is cross-compatible 
    hours_query = db.session.query(
        db.extract('hour', IDFinderMessage.timestamp).label('hour'),
        func.count(IDFinderMessage.id).label('count')
    ).filter(query_filter).group_by('hour').all()
    
    busiest_hours = [0] * 24
    for row in hours_query:
        if row.hour is not None:
            busiest_hours[int(row.hour)] = row.count

    # Weekdays distribution
    # Extract 'dow' works across most dialects (0=Sun, 1=Mon... in some, or 1=Sun in others).
    # MySQL: 1=Sun, 2=Mon
    # SQLite: 0=Sun, 1=Mon
    dow_query = db.session.query(
        db.extract('dow', IDFinderMessage.timestamp).label('dow'),
        func.count(IDFinderMessage.id).label('count')
    ).filter(query_filter).group_by('dow').all()

    busiest_days = [0] * 7
    for row in dow_query:
        if row.dow is not None:
            engine_name = db.engine.dialect.name
            if engine_name == 'mysql':
                # Shift MySQL 1-7 (Sun-Sat) to 0-6 (Mon-Sun)
                py_dow = (int(row.dow) + 5) % 7
            else:
                # Shift SQLite 0-6 (Sun-Sat) to 0-6 (Mon-Sun)
                py_dow = (int(row.dow) + 6) % 7
            busiest_days[py_dow] = row.count

    return render_template('id_finder_analytics.html', 
                           stats={'total_users': total_users}, 
                           activity={
                               'timeline': {'labels': timeline_labels, 'total': total_data}, 
                               'leaderboard': leaderboard, 
                               'busiest_hours': busiest_hours, 
                               'busiest_days': busiest_days
                           })

@bp.route('/api/id-finder/user-activity/<int:uid>')
def id_finder_user_activity(uid):
    try:
        days = int(request.args.get('days') or 7)
    except ValueError:
        days = 7

    now = datetime.utcnow()
    cutoff = now - timedelta(days=days)
    
    timeline_query = db.session.query(
        func.date(IDFinderMessage.timestamp).label('date'),
        func.count(IDFinderMessage.id).label('count')
    ).filter(IDFinderMessage.telegram_user_id == uid, IDFinderMessage.timestamp >= cutoff) \
     .group_by('date').order_by('date').all()

    date_map = {row.date.strftime('%d.%m'): row.count for row in timeline_query if row.date}
    
    total_data = []
    for i in range(days-1, -1, -1):
        d_str = (now - timedelta(days=i)).strftime('%d.%m')
        total_data.append(date_map.get(d_str, 0))

    return jsonify({"timeline": total_data})

# --- USER MANAGEMENT ---
@bp.route('/users')
def manage_users():
    us = User.query.all(); ud = {u.username: {'role': u.role} for u in us}
    return render_template('manage_users.html', users=ud)

@bp.route('/users/add', methods=['POST'])
def add_user():
    u, p, r = request.form.get('username'), request.form.get('password'), request.form.get('role', 'user')
    if u and p and not User.query.filter_by(username=u).first():
        nu = User(username=u, role=r); nu.set_password(p); db.session.add(nu); db.session.commit()
    return redirect(url_for('dashboard.manage_users'))

@bp.route('/users/delete/<username>', methods=['POST'])
def delete_user(username):
    u = User.query.filter_by(username=username).first()
    if u: db.session.delete(u); db.session.commit()
    return redirect(url_for('dashboard.manage_users'))

@bp.route('/users/edit/<username>', methods=['POST'])
def edit_user(username):
    u = User.query.filter_by(username=username).first()
    if u:
        nu, np, nr = request.form.get('new_username'), request.form.get('new_password'), request.form.get('new_role')
        if nu: u.username = nu
        if np: u.set_password(np)
        if nr: u.role = nr
        db.session.commit()
    return redirect(url_for('dashboard.manage_users'))

# --- MINECRAFT ---
@bp.route('/minecraft')
def minecraft_status_page(): return render_template('minecraft_status.html', cfg=None)

# --- TIKTOK BOT ---
@bp.route('/tiktok-settings', methods=['GET', 'POST'])
def tiktok_settings():
    s = BotSettings.query.filter_by(bot_name='tiktok_bot').first()
    if not s:
        cfg = {'telegram_chat_id': '', 'telegram_topic_id': '', 'target_unique_ids': [], 'watch_hosts': [], 'retry_offline_seconds': 60, 'alert_cooldown_seconds': 1800, 'max_concurrent_lives': 3, 'is_active': False, 'message_template_self': "🔴 {target} ist LIVE!", 'message_template_presence': "👀 {target} bei @{host}!"}
        s = BotSettings(bot_name='tiktok_bot', config_json=json.dumps(cfg)); db.session.add(s); db.session.commit()
    
    cfg = json.loads(s.config_json)
    if request.method == 'POST':
        cfg.update({'telegram_chat_id': request.form.get('telegram_chat_id'), 'telegram_topic_id': request.form.get('telegram_topic_id'), 'target_unique_ids': [t.strip().lstrip('@') for t in request.form.getlist('target_unique_ids') if t.strip()], 'watch_hosts': [h.strip().lstrip('@') for h in request.form.get('watch_hosts', '').split(',') if h.strip()], 'message_template_self': request.form.get('message_template_self'), 'message_template_presence': request.form.get('message_template_presence'), 'alert_cooldown_seconds': int(request.form.get('alert_cooldown_seconds', 1800)), 'max_concurrent_lives': int(request.form.get('max_concurrent_lives', 3))})
        s.config_json = json.dumps(cfg); db.session.commit(); flash('TikTok-Einstellungen gespeichert.', 'success'); return redirect(url_for('dashboard.tiktok_settings'))

    logs = []
    if os.path.exists(TIKTOK_BOT_LOG_FILE):
        with open(TIKTOK_BOT_LOG_FILE, 'r') as f: logs = f.readlines()[-100:]
    
    ids = BotSettings.query.filter_by(bot_name='id_finder').first()
    cfg['api_token_display'] = json.loads(ids.config_json).get('bot_token', 'Nicht gesetzt') if ids else 'Nicht gesetzt'
    return render_template('tiktok_settings.html', config=cfg, logs=logs)

@bp.route('/tiktok/clear-logs', methods=['POST'])
def tiktok_clear_logs():
    if os.path.exists(TIKTOK_BOT_LOG_FILE): open(TIKTOK_BOT_LOG_FILE, 'w').close()
    return redirect(url_for('dashboard.tiktok_settings'))

# --- BOT ACTIONS ---
@bp.route('/bot-action/<bot_name>/<action>', methods=['POST'])
def bot_action_route(bot_name, action):
    pfile, script, lpath = None, None, None
    if bot_name == 'id_finder': pfile, script, lpath = ID_FINDER_BOT_PID_FILE, os.path.join(PROJECT_ROOT, "bots", "id_finder_bot", "id_finder_bot.py"), ID_FINDER_BOT_LOG_FILE
    elif bot_name == 'tiktok': pfile, script, lpath = TIKTOK_BOT_PID_FILE, os.path.join(PROJECT_ROOT, "bots", "tiktok_bot", "tiktok_bot.py"), TIKTOK_BOT_LOG_FILE
    
    if pfile and script:
        if action == 'start':
            # Check common Windows/Linux venv paths
            exe = sys.executable
            venv_win = os.path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe")
            venv_lin = os.path.join(PROJECT_ROOT, ".venv", "bin", "python")
            old_venv_win = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
            old_venv_lin = os.path.join(PROJECT_ROOT, "venv", "bin", "python")
            
            if os.path.exists(venv_win): exe = venv_win
            elif os.path.exists(venv_lin): exe = venv_lin
            elif os.path.exists(old_venv_win): exe = old_venv_win
            elif os.path.exists(old_venv_lin): exe = old_venv_lin

            os.makedirs(os.path.dirname(lpath), exist_ok=True)
            env = os.environ.copy(); env["PYTHONUNBUFFERED"] = "1"
            
            # Use creationflags on Windows to detach the process properly
            creationflags = 0
            if os.name == 'nt':
                creationflags = 0x00000008  # CREATE_NO_WINDOW
                
            with open(lpath, 'a', encoding='utf-8') as lf: 
                proc = subprocess.Popen([exe, script], start_new_session=(os.name != 'nt'), creationflags=creationflags, stdout=lf, stderr=lf, env=env)
            with open(pfile, 'w') as f: f.write(str(proc.pid))
            s = BotSettings.query.filter_by(bot_name=f"{bot_name}_bot").first()
            if s: c = json.loads(s.config_json); c['is_active'] = True; s.config_json = json.dumps(c); db.session.commit()
            flash(f'{bot_name} Bot gestartet.', 'success')
        elif action == 'stop' and os.path.exists(pfile):
            try:
                with open(pfile, 'r') as f: pid = int(f.read().strip())
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.kill(pid, signal.SIGTERM)
                os.remove(pfile)
            except Exception as e:
                print(f"Fehler beim Stoppen von {bot_name} (PID: {pid}): {e}")
            finally:
                # Always update the database so the dashboard doesn't get stuck showing "Running"
                s = BotSettings.query.filter_by(bot_name=f"{bot_name}_bot").first()
                if s: 
                    c = json.loads(s.config_json)
                    c['is_active'] = False
                    s.config_json = json.dumps(c)
                    db.session.commit()
                flash(f'{bot_name} Bot Befehl gesendet.', 'success')
    return redirect(request.referrer or url_for('dashboard.index'))

@bp.route('/api/bot-status')
def bot_status_api(): return jsonify(get_bot_status_simple())

@bp.route('/api/dashboard/save-layout', methods=['POST'])
def save_dashboard_layout_api():
    data = request.json
    s = BotSettings.query.filter_by(bot_name='dashboard_layout').first()
    if not s: s = BotSettings(bot_name='dashboard_layout', config_json=json.dumps(data)); db.session.add(s)
    else: s.config_json = json.dumps(data)
    db.session.commit()
    return jsonify({"success": True})
