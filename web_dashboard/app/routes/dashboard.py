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

bp = Blueprint('dashboard', __name__)

# Fixed PROJECT_ROOT to point to the actual project root
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
        "invite": {"running": False},
        "quiz": {"running": False},
        "umfrage": {"running": False},
        "outfit": {"running": False},
        "id_finder": {"running": False},
        "tiktok": {"running": False}
    }
    
    def check_bot_pid(bot_key, pid_file):
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    pid = int(f.read().strip())
                if is_process_running(pid):
                    status[bot_key]["running"] = True
                else:
                    os.remove(pid_file)
            except:
                if os.path.exists(pid_file): os.remove(pid_file)

    check_bot_pid("invite", INVITE_BOT_PID_FILE)
    check_bot_pid("id_finder", ID_FINDER_BOT_PID_FILE)
    check_bot_pid("tiktok", TIKTOK_BOT_PID_FILE)
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
    layout = None
    if layout_settings:
        try: layout = json.loads(layout_settings.config_json)
        except: pass
    return render_template('index.html', version=version, layout=layout)

@bp.route('/bot-action/<bot_name>/<action>', methods=['POST'])
def bot_action_route(bot_name, action):
    pid_file = None
    bot_script = None
    log_file_path = None
    flash_name = bot_name

    if bot_name == 'id_finder':
        pid_file = ID_FINDER_BOT_PID_FILE
        bot_script = os.path.join(PROJECT_ROOT, "bots", "id_finder_bot", "id_finder_bot.py")
        log_file_path = ID_FINDER_BOT_LOG_FILE
        flash_name = "ID-Finder"
    elif bot_name == 'tiktok':
        pid_file = TIKTOK_BOT_PID_FILE
        bot_script = os.path.join(PROJECT_ROOT, "bots", "tiktok_bot", "tiktok_bot.py")
        log_file_path = TIKTOK_BOT_LOG_FILE
        flash_name = "TikTok"
    
    if pid_file and bot_script:
        if action == 'start':
            if os.path.exists(pid_file):
                 try:
                    pid_val = int(open(pid_file).read().strip())
                    if is_process_running(pid_val): flash(f'{flash_name} läuft bereits.', 'warning'); return redirect(request.referrer or url_for('dashboard.index'))
                    else: os.remove(pid_file)
                 except: os.remove(pid_file)
            try:
                exe_to_use = os.path.join(PROJECT_ROOT, "venv", "bin", "python")
                if not os.path.exists(exe_to_use): exe_to_use = sys.executable
                os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"
                with open(log_file_path, 'a') as log_f: 
                    process = subprocess.Popen([exe_to_use, bot_script], start_new_session=True, stdout=log_f, stderr=log_f, env=env)
                with open(pid_file, 'w') as f: f.write(str(process.pid))
                settings = BotSettings.query.filter_by(bot_name=f"{bot_name}_bot").first()
                if settings:
                    config = json.loads(settings.config_json)
                    config['is_active'] = True
                    settings.config_json = json.dumps(config)
                    db.session.commit()
                flash(f'{flash_name} Bot gestartet.', 'success')
            except Exception as e: flash(f'Fehler beim Starten: {e}', 'danger')
        elif action == 'stop':
            if os.path.exists(pid_file):
                try:
                    with open(pid_file, 'r') as f: pid = int(f.read().strip())
                    os.kill(pid, signal.SIGTERM); os.remove(pid_file)
                    settings = BotSettings.query.filter_by(bot_name=f"{bot_name}_bot").first()
                    if settings:
                        config = json.loads(settings.config_json)
                        config['is_active'] = False
                        settings.config_json = json.dumps(config)
                        db.session.commit()
                    flash(f'{flash_name} Bot gestoppt.', 'success')
                except Exception as e: flash(f'Fehler beim Stoppen: {e}', 'danger')
    return redirect(request.referrer or url_for('dashboard.index'))

# --- TikTok Bot Logic ---

def get_tiktok_bot_settings():
    settings = BotSettings.query.filter_by(bot_name='tiktok_bot').first()
    if not settings:
        initial_config = {
            'telegram_chat_id': '',
            'telegram_topic_id': '',
            'target_unique_ids': [], # Neu: Liste für mehrere Targets
            'watch_hosts': [],
            'retry_offline_seconds': 60,
            'alert_cooldown_seconds': 1800,
            'max_concurrent_lives': 3,
            'is_active': False,
            'message_template_self': "🔴 {target} ist jetzt LIVE!\n\n🔗 {url}",
            'message_template_presence': "👀 {target} wurde in einem TikTok-Live gesehen!\n\n🎥 Host: @{host}\n📌 Event: {event}\n🔗 {url}"
        }
        settings = BotSettings(bot_name='tiktok_bot', config_json=json.dumps(initial_config))
        db.session.add(settings)
        db.session.commit()
    return settings

@bp.route('/tiktok-settings', methods=['GET', 'POST'])
def tiktok_settings():
    settings = get_tiktok_bot_settings()
    config = json.loads(settings.config_json)
    
    id_finder_settings = BotSettings.query.filter_by(bot_name='id_finder').first()
    id_finder_config = json.loads(id_finder_settings.config_json) if id_finder_settings else {}
    config['api_token_display'] = id_finder_config.get('bot_token', 'Nicht gesetzt')

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'save_settings':
            config['telegram_chat_id'] = request.form.get('telegram_chat_id')
            config['telegram_topic_id'] = request.form.get('telegram_topic_id')
            
            # Neu: Mehrere Targets auslesen
            targets_raw = request.form.getlist('target_unique_ids')
            config['target_unique_ids'] = [t.strip().lstrip('@') for t in targets_raw if t.strip()]
            
            hosts_raw = request.form.get('watch_hosts', '')
            config['watch_hosts'] = [h.strip().lstrip('@') for h in hosts_raw.split(',') if h.strip()]
            
            config['message_template_self'] = request.form.get('message_template_self')
            config['message_template_presence'] = request.form.get('message_template_presence')
            try: config['alert_cooldown_seconds'] = int(request.form.get('alert_cooldown_seconds', 1800))
            except: pass
            try: config['max_concurrent_lives'] = int(request.form.get('max_concurrent_lives', 3))
            except: pass
            
            config.pop('api_token_display', None)
            settings.config_json = json.dumps(config)
            db.session.commit()
            flash('TikTok-Einstellungen gespeichert.', 'success')
            return redirect(url_for('dashboard.tiktok_settings'))

    logs = []
    if os.path.exists(TIKTOK_BOT_LOG_FILE):
        try:
            with open(TIKTOK_BOT_LOG_FILE, 'r', encoding='utf-8') as f: logs = f.readlines()[-100:]
        except: pass
    return render_template('tiktok_settings.html', config=config, logs=logs)

@bp.route('/tiktok/clear-logs', methods=['POST'])
def tiktok_clear_logs():
    if os.path.exists(TIKTOK_BOT_LOG_FILE):
        try:
            with open(TIKTOK_BOT_LOG_FILE, 'w') as f: f.write('')
            flash('TikTok-Logs gelöscht.', 'success')
        except: pass
    return redirect(url_for('dashboard.tiktok_settings'))

# --- End TikTok Bot Logic ---

@bp.route('/minecraft', methods=['GET', 'POST'])
def minecraft_status_page(): return render_template('minecraft_status.html', cfg=None)

@bp.route('/users')
def manage_users():
    users = User.query.all(); users_dict = {u.username: {'role': u.role} for u in users}
    return render_template('manage_users.html', users=users_dict)
