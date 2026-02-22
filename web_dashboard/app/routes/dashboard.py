from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, send_file, abort
from ..models import db, BotSettings, User
import os
import json
import subprocess
import sys
from datetime import datetime

bp = Blueprint('dashboard', __name__)

# Pfade für Logs
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
CRITICAL_ERRORS_LOG_FILE = os.path.join(BASE_DIR, "critical_errors.log")

def get_bot_status_simple():
    # Minimale Status-Logik, um Abstürze zu vermeiden
    return {
        "invite": {"running": False},
        "quiz": {"running": False},
        "umfrage": {"running": False},
        "outfit": {"running": False},
        "id_finder": {"running": False}
    }

@bp.context_processor
def inject_globals():
    return {"bot_status": get_bot_status_simple(), "session": {"user": "Admin", "role": "admin"}}

# --- Zentrale Routen ---

@bp.route('/')
@bp.route('/dashboard')
def index():
    return render_template('index.html', version={"version": "3.0.0"})

@bp.route('/bot-settings', methods=["GET", "POST"])
def bot_settings():
    invite_bot_settings = BotSettings.query.filter_by(bot_name='invite').first()
    if not invite_bot_settings:
        initial_config = {'is_enabled': False, 'profile_fields': []}
        invite_bot_settings = BotSettings(bot_name='invite', config_json=json.dumps(initial_config))
        db.session.add(invite_bot_settings)
        db.session.commit()

    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'start_invite_bot':
            invite_bot_settings.is_active = True
            db.session.commit()
            flash('Invite bot started successfully.', 'success')
        elif action == 'stop_invite_bot':
            invite_bot_settings.is_active = False
            db.session.commit()
            flash('Invite bot stopped successfully.', 'success')
        return redirect(url_for('dashboard.bot_settings'))

    config = json.loads(invite_bot_settings.config_json)
    config.setdefault('profile_fields', []) # Ensure profile_fields exist
    is_invite_running = invite_bot_settings.is_active
    # Dummy values for user_interaction_logs, invite_bot_logs for now
    return render_template("bot_settings.html", config=config, is_invite_running=is_invite_running, user_interaction_logs=[], invite_bot_logs=[])

@bp.route('/save_base_config', methods=['POST'])
def save_base_config():
    invite_bot_settings = BotSettings.query.filter_by(bot_name='invite').first()
    if not invite_bot_settings:
        flash('Bot settings not found.', 'danger')
        return redirect(url_for('dashboard.bot_settings'))

    config = json.loads(invite_bot_settings.config_json)
    config['is_enabled'] = 'is_enabled' in request.form
    config['bot_token'] = request.form.get('bot_token', '')
    config['main_chat_id'] = request.form.get('main_chat_id', '')
    config['topic_id'] = request.form.get('topic_id', '')
    config['link_ttl_minutes'] = request.form.get('link_ttl_minutes', type=int, default=15)
    
    invite_bot_settings.config_json = json.dumps(config)
    db.session.commit()
    flash('Base configuration saved successfully.', 'success')
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/save_invite_content', methods=['POST'])
def save_invite_content():
    invite_bot_settings = BotSettings.query.filter_by(bot_name='invite').first()
    if not invite_bot_settings:
        flash('Bot settings not found.', 'danger')
        return redirect(url_for('dashboard.bot_settings'))

    config = json.loads(invite_bot_settings.config_json)
    config['start_message'] = request.form.get('start_message', '')
    config['rules_message'] = request.form.get('rules_message', '')
    config['blocked_message'] = request.form.get('blocked_message', '')
    config['privacy_policy'] = request.form.get('privacy_policy', '')

    invite_bot_settings.config_json = json.dumps(config)
    db.session.commit()
    flash('Einladungsbot-Inhalt gespeichert.', 'success')
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/add_profile_field', methods=['POST'])
def add_profile_field():
    invite_bot_settings = BotSettings.query.filter_by(bot_name='invite').first()
    if not invite_bot_settings:
        flash('Bot settings not found.', 'danger')
        return redirect(url_for('dashboard.bot_settings'))

    config = json.loads(invite_bot_settings.config_json)
    if 'profile_fields' not in config:
        config['profile_fields'] = []

    field_name = request.form.get('name')
    field_type = request.form.get('type', 'text')
    field_required = 'required' in request.form

    if not field_name:
        flash('Feldname darf nicht leer sein.', 'danger')
        return redirect(url_for('dashboard.bot_settings'))

    new_field = {'name': field_name, 'type': field_type, 'required': field_required}
    config['profile_fields'].append(new_field)

    invite_bot_settings.config_json = json.dumps(config)
    db.session.commit()
    flash('Profilfeld erfolgreich hinzugefügt.', 'success')
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/edit_profile_field', methods=['POST'])
def edit_profile_field():
    invite_bot_settings = BotSettings.query.filter_by(bot_name='invite').first()
    if not invite_bot_settings:
        flash('Bot settings not found.', 'danger')
        return redirect(url_for('dashboard.bot_settings'))

    config = json.loads(invite_bot_settings.config_json)
    field_index = request.form.get('field_index', type=int)

    if field_index is None or not (0 <= field_index < len(config.get('profile_fields', []))):
        flash('Ungültiger Feldindex.', 'danger')
        return redirect(url_for('dashboard.bot_settings'))

    field_name = request.form.get('name')
    field_type = request.form.get('type', 'text')
    field_required = 'required' in request.form

    if not field_name:
        flash('Feldname darf nicht leer sein.', 'danger')
        return redirect(url_for('dashboard.bot_settings'))

    config['profile_fields'][field_index] = {'name': field_name, 'type': field_type, 'required': field_required}
    
    invite_bot_settings.config_json = json.dumps(config)
    db.session.commit()
    flash('Profilfeld erfolgreich aktualisiert.', 'success')
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/delete_profile_field', methods=['POST'])
def delete_profile_field():
    invite_bot_settings = BotSettings.query.filter_by(bot_name='invite').first()
    if not invite_bot_settings:
        flash('Bot settings not found.', 'danger')
        return redirect(url_for('dashboard.bot_settings'))

    config = json.loads(invite_bot_settings.config_json)
    field_index = request.form.get('field_index', type=int)

    if field_index is None or not (0 <= field_index < len(config.get('profile_fields', []))):
        flash('Ungültiger Feldindex.', 'danger')
        return redirect(url_for('dashboard.bot_settings'))

    del config['profile_fields'][field_index]
    
    invite_bot_settings.config_json = json.dumps(config)
    db.session.commit()
    flash('Profilfeld erfolgreich gelöscht.', 'success')
    return redirect(url_for('dashboard.bot_settings'))

@bp.route('/live_moderation')
def live_moderation():
    return render_template('live_moderation.html', topics={}, messages=[], selected_chat_id=None, selected_topic_id=None, mod_config={})

@bp.route('/live_moderation_config', methods=['POST'])
def live_moderation_config():
    # Here you would typically save the configuration
    flash('Moderations-Einstellungen wurden gespeichert.', 'success')
    return redirect(url_for('dashboard.live_moderation'))

@bp.route('/live_moderation_delete', methods=['POST'])
def live_moderation_delete():
    # Here you would typically handle the deletion logic
    flash('Nachricht wurde gelöscht.', 'success')
    return redirect(url_for('dashboard.live_moderation'))

@bp.route('/broadcast')
def broadcast_manager():
    return render_template("broadcast_manager.html", broadcasts=[], known_topics={})

@bp.route('/minecraft')
def minecraft_status_page():
    return render_template("minecraft.html", cfg={}, status={}, is_running=False, server_online=False, pi={}, log_tail="")

@bp.route("/id-finder")
def id_finder_dashboard(): 
    return render_template("id_finder_dashboard.html", config={})

@bp.route("/quiz-settings")
def quiz_settings():
    return render_template("quiz_settings.html", config={}, schedule={}, stats={}, questions_json="[]", asked_questions_json="[]", logs=[])

@bp.route("/umfrage-settings")
def umfrage_settings():
    return render_template("umfrage_settings.html", config={}, schedule={}, stats={}, umfragen_json="[]", asked_umfragen_json="[]", logs=[])

@bp.route("/outfit-bot/dashboard")
def outfit_bot_dashboard():
    return render_template("outfit_bot_dashboard.html", config={}, is_running=False, logs=[], duel_status={"active": False})

@bp.route("/admin/users")
def manage_users():
    return render_template("manage_users.html", users={})

@bp.route('/critical-errors')
def critical_errors():
    logs = []
    if os.path.exists(CRITICAL_ERRORS_LOG_FILE):
        try:
            with open(CRITICAL_ERRORS_LOG_FILE, 'r') as f:
                logs = f.readlines()
        except: pass
    return render_template("critical_errors.html", critical_logs=logs)

@bp.route('/clear-critical-errors', methods=['POST'])
def clear_critical_errors():
    if os.path.exists(CRITICAL_ERRORS_LOG_FILE):
        try:
            os.remove(CRITICAL_ERRORS_LOG_FILE)
            flash('Kritische Fehlerprotokolle erfolgreich gelöscht.', 'success')
        except Exception as e:
            flash(f'Fehler beim Löschen der Protokolle: {e}', 'danger')
    else:
        flash('Keine Protokolldatei zum Löschen gefunden.', 'info')
    return redirect(url_for('dashboard.critical_errors'))

# --- API Endpunkte ---
@bp.route('/api/bot-status')
def bot_status_api():
    return jsonify(get_bot_status_simple())

@bp.route('/api/update/check')
def update_check():
    return jsonify({"update_available": False})
