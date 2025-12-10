
import os
import random
import json
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import atexit
import threading
import subprocess
from datetime import datetime
import sys

from flask import Flask, render_template, request, flash, redirect, url_for

# --- Logging (Global & App) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
    handlers=[
        RotatingFileHandler('app.log', maxBytes=10240, backupCount=5),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)
log = logging.getLogger(__name__)

# --- Flask App Initialisierung ---
app = Flask(__name__, template_folder='src')
app.secret_key = 'b13f172933b9a1274adb024d47fc7552d2e85864693cb9a2'
app.config['TEMPLATES_AUTO_RELOAD'] = True

# --- Globale Variablen & Dateipfade ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

OUTFIT_BOT_DIR = os.path.join(PROJECT_ROOT, 'outfit_bot')
OUTFIT_BOT_CONFIG_FILE = os.path.join(OUTFIT_BOT_DIR, 'outfit_bot_config.json')
OUTFIT_BOT_SCRIPT = os.path.join(OUTFIT_BOT_DIR, 'outfit_bot.py')
OUTFIT_BOT_LOG = os.path.join(OUTFIT_BOT_DIR, 'outfit_bot.log')
OUTFIT_BOT_DATA_FILE = os.path.join(OUTFIT_BOT_DIR, 'outfit_bot_data.json')

# --- Prozess-Variablen ---
outfit_bot_process = None

# --- Hilfsfunktionen für JSON ---
def load_json(file_path, default_data={}):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0: return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
    except json.JSONDecodeError: return default_data

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

# --- Bot Management Helper ---
def is_bot_running(process):
    return process and process.poll() is None

def get_bot_logs(log_file, lines=100):
    if not os.path.exists(log_file): return ["Keine Log-Datei vorhanden."]
    try:
        with open(log_file, 'r', encoding='utf-8') as f: return list(reversed(f.readlines()[-lines:]))
    except Exception as e: return [f"Fehler beim Lesen der Logs: {e}"]

def start_bot_process(script_path, log_path):
    global outfit_bot_process
    if is_bot_running(outfit_bot_process):
        return outfit_bot_process, f"{os.path.basename(script_path)} läuft bereits."
    try:
        cwd = os.path.dirname(script_path)
        py_exec = sys.executable
        with open(log_path, "a", encoding="utf-8") as log_f:
            process = subprocess.Popen([py_exec, script_path], cwd=cwd, stdout=log_f, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
        return process, f"{os.path.basename(script_path)} erfolgreich gestartet."
    except Exception as e:
        return None, str(e)

def stop_bot_process(process):
    if not process or process.poll() is not None: return None, "Bot läuft nicht."
    try:
        process.terminate()
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
    return None, "Bot erfolgreich gestoppt."

# --- Outfit Bot Wrappers ---
def is_outfit_bot_running(): return is_bot_running(outfit_bot_process)
def start_outfit_bot():
    global outfit_bot_process
    outfit_bot_process, msg = start_bot_process(OUTFIT_BOT_SCRIPT, OUTFIT_BOT_LOG)
    return bool(outfit_bot_process), msg
def stop_outfit_bot():
    global outfit_bot_process
    outfit_bot_process, msg = stop_bot_process(outfit_bot_process)
    return not bool(outfit_bot_process), msg
def get_outfit_bot_logs(lines=30): return get_bot_logs(OUTFIT_BOT_LOG, lines)

# --- ROUTEN ---
@app.route("/")
def index():
    return redirect(url_for('outfit_bot_dashboard'))

@app.route("/outfit-bot/dashboard")
def outfit_bot_dashboard():
    config = load_json(OUTFIT_BOT_CONFIG_FILE)
    duel_status = {"active": False}
    bot_data = load_json(OUTFIT_BOT_DATA_FILE)
    if bot_data and "current_duel" in bot_data:
        duel_data = bot_data["current_duel"]
        contestants = duel_data.get("contestants", {})
        names = [f"@{d.get('username', 'Unbekannt')}" for d in contestants.values()]
        duel_status["active"] = True
        duel_status["contestants"] = " vs ".join(names)
        
    return render_template('outfit_bot_dashboard.html', config=config, is_running=is_outfit_bot_running(), logs=get_outfit_bot_logs(30), duel_status=duel_status)

@app.route("/outfit-bot/start", methods=['POST'])
def outfit_bot_start():
    success, msg = start_outfit_bot()
    flash(msg, "success" if success else "danger")
    return redirect(url_for('outfit_bot_dashboard'))

@app.route("/outfit-bot/stop", methods=['POST'])
def outfit_bot_stop():
    success, msg = stop_outfit_bot()
    flash(msg, "success" if success else "danger")
    return redirect(url_for('outfit_bot_dashboard'))

@app.route("/outfit-bot/clear-logs", methods=['POST'])
def outfit_bot_clear_logs():
    try:
        with open(OUTFIT_BOT_LOG, 'w') as f:
            f.write('')
        flash("Logs erfolgreich geleert.", "success")
    except Exception as e:
        flash(f"Fehler beim Leeren der Logs: {e}", "danger")
    return redirect(url_for('outfit_bot_dashboard'))

@app.route("/outfit-bot/save-config", methods=['POST'])
def outfit_bot_save_config():
    was_running = is_outfit_bot_running()
    if was_running:
        stop_outfit_bot()

    config = load_json(OUTFIT_BOT_CONFIG_FILE)
    form = request.form
    
    config.update({
        'BOT_TOKEN': form.get('BOT_TOKEN', '').strip(),
        'CHAT_ID': form.get('CHAT_ID', '').strip(),
        'TOPIC_ID': form.get('TOPIC_ID', '').strip() or None,
        'POST_TIME': form.get('POST_TIME', '18:00'),
        'WINNER_TIME': form.get('WINNER_TIME', '22:00'),
        'DUEL_TYPE': form.get('DUEL_TYPE', 'tie_breaker'),
        'DUEL_DURATION_MINUTES': int(form.get('DUEL_DURATION_MINUTES', 60)),
        'TEMPORARY_MESSAGE_DURATION_SECONDS': int(form.get('TEMPORARY_MESSAGE_DURATION_SECONDS', 30)) # NEW: Save temporary message duration
    })

    config['AUTO_POST_ENABLED'] = 'AUTO_POST_ENABLED' in form
    config['DUEL_MODE'] = 'DUEL_MODE' in form

    admin_ids_str = form.get('ADMIN_USER_IDS', '')
    try:
        config['ADMIN_USER_IDS'] = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip().isdigit()]
    except ValueError:
        flash("Fehler: Ungültige Admin User ID.", "danger")
        return redirect(url_for('outfit_bot_dashboard'))

    save_json(OUTFIT_BOT_CONFIG_FILE, config)
    flash("Konfiguration gespeichert!", "success")

    if was_running:
        success, msg = start_outfit_bot()
        flash("Bot wird mit neuer Konfiguration neu gestartet.", "info")

    return redirect(url_for('outfit_bot_dashboard'))

@app.route("/outfit-bot/start-contest", methods=['POST'])
def outfit_bot_start_contest():
    if is_outfit_bot_running():
        with open(os.path.join(OUTFIT_BOT_DIR, "command_start_contest.tmp"), 'w') as f: f.write('trigger')
        flash("Befehl 'Wettbewerb starten' gesendet.", "info")
    else:
        flash("Bot läuft nicht!", "danger")
    return redirect(url_for('outfit_bot_dashboard'))

@app.route("/outfit-bot/announce-winner", methods=['POST'])
def outfit_bot_announce_winner():
    if is_outfit_bot_running():
        with open(os.path.join(OUTFIT_BOT_DIR, "command_announce_winner.tmp"), 'w') as f: f.write('trigger')
        flash("Befehl 'Gewinner auslosen' gesendet.", "info")
    else:
        flash("Bot läuft nicht!", "danger")
    return redirect(url_for('outfit_bot_dashboard'))

@app.route("/outfit-bot/end-duel", methods=['POST'])
def outfit_bot_end_duel():
    if is_outfit_bot_running():
        with open(os.path.join(OUTFIT_BOT_DIR, "command_end_duel.tmp"), 'w') as f: f.write('trigger')
        flash("Befehl 'Duell beenden' gesendet.", "info")
    else:
        flash("Bot läuft nicht!", "danger")
    return redirect(url_for('outfit_bot_dashboard'))

# --- Auto-Start & Shutdown ---
def shutdown_background_processes():
    stop_outfit_bot()

if __name__ == '__main__':
    atexit.register(shutdown_background_processes)
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
