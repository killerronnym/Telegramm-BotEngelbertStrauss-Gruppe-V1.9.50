
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

from flask import Flask, render_template, request, flash, redirect, url_for, render_template_string
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
    handlers=[RotatingFileHandler('app.log', maxBytes=10240, backupCount=5), logging.StreamHandler()],
    force=True
)
log = logging.getLogger(__name__)

# --- Globale Variablen ---
app = Flask(__name__, template_folder='src')
app.secret_key = os.urandom(24)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Dateipfade
CONFIG_FILE = 'config.json'
OUTFIT_BOT_CONFIG_FILE = 'outfit_bot_config.json'
OUTFIT_BOT_SCRIPT = 'outfit_bot.py'
OUTFIT_BOT_LOG = 'outfit_bot.log' # Logdatei des Bots
QUIZFRAGEN_FILE = 'quizfragen.json'
GESTELLTE_QUIZFRAGEN_FILE = 'gestellte_quizfragen.json'
UMFRAGEN_FILE = 'umfragen.json'
GESTELLTE_UMFRAGEN_FILE = 'gestellte_umfragen.json'

# Prozess-Variablen
outfit_bot_process = None

# --- Hilfsfunktionen für JSON ---
def load_json(file_path, default_data):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0: return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
    except json.JSONDecodeError: return default_data

def save_json(file_path, data): 
    with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4, ensure_ascii=False)

def load_config():
    default = {"quiz": {}, "umfrage": {}}
    return load_json(CONFIG_FILE, default)

# --- Hilfsfunktionen für Outfit-Bot Management ---
def is_outfit_bot_running():
    global outfit_bot_process
    if outfit_bot_process and outfit_bot_process.poll() is None:
        return True
    return False

def get_outfit_bot_logs(lines=30):
    if not os.path.exists(OUTFIT_BOT_LOG):
        return ["Keine Log-Datei vorhanden."]
    try:
        with open(OUTFIT_BOT_LOG, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    except Exception as e:
        return [f"Fehler beim Lesen der Logs: {e}"]

def start_outfit_bot():
    global outfit_bot_process
    # Dies ist der Schlüssel: Nur starten, wenn WERKZEUG_RUN_MAIN == 'true'
    # Sonst startet es doppelt im Flask Debug Modus
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        log.info("start_outfit_bot: Nicht im Haupt-Worker-Prozess, überspringe Start.")
        return False, "Nicht im Hauptprozess, Bot wird hier nicht gestartet."

    if is_outfit_bot_running():
        return False, "Bot läuft bereits."
    try:
        python_executable = __import__('sys').executable
        outfit_bot_process = subprocess.Popen([python_executable, OUTFIT_BOT_SCRIPT])
        log.info(f"{OUTFIT_BOT_SCRIPT} gestartet mit PID: {outfit_bot_process.pid}")
        return True, "Bot erfolgreich gestartet."
    except Exception as e:
        log.error(f"Fehler beim Starten des Bots: {e}", exc_info=True)
        return False, f"Fehler beim Starten: {e}"

def stop_outfit_bot():
    global outfit_bot_process
    if not is_outfit_bot_running():
        return False, "Bot läuft nicht."
    try:
        outfit_bot_process.terminate()
        try:
            outfit_bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            outfit_bot_process.kill()
        outfit_bot_process = None
        log.info("Outfit-Bot Prozess gestoppt.")
        return True, "Bot erfolgreich gestoppt."
    except Exception as e:
        log.error(f"Fehler beim Stoppen des Bots: {e}", exc_info=True)
        return False, f"Fehler beim Stoppen: {e}"


# --- Haupt-Web-Routen ---
@app.route("/")
def index():
    return render_template('index.html', config=load_config())

# ... (Alte Quiz-Routen bleiben unverändert) ...
async def send_telegram_poll(bot_token, channel_id, question, options, poll_type, correct_option_id=None, is_anonymous=True):
    try:
        bot = telegram.Bot(token=bot_token)
        await bot.send_poll(chat_id=channel_id, question=question, options=options, type=poll_type, correct_option_id=correct_option_id, is_anonymous=is_anonymous)
        return True, None
    except Exception as e: return False, str(e)

@app.route('/send_quizfrage', methods=['POST'])
def send_quizfrage_route():
    config = load_config().get('quiz', {})
    bot_token, channel_id = config.get('token'), config.get('channel_id')
    if not bot_token or not channel_id: return redirect(url_for('index'))
    all_q = load_json(QUIZFRAGEN_FILE, [])
    asked_q_ids = load_json(GESTELLTE_QUIZFRAGEN_FILE, [])
    for i, q in enumerate(all_q): 
        if 'id' not in q: q['id'] = i
    available = [q for q in all_q if q.get('id') not in asked_q_ids]
    if not available:
        asked_q_ids = []
        save_json(GESTELLTE_QUIZFRAGEN_FILE, asked_q_ids)
        available = all_q
    if not available: return redirect(url_for('index'))
    question = random.choice(available)
    success, error = asyncio.run(send_telegram_poll(bot_token, channel_id, question.get('frage'), question.get('optionen'), 'quiz', correct_option_id=question.get('antwort'), is_anonymous=True))
    if success:
        asked_q_ids.append(question['id'])
        save_json(GESTELLTE_QUIZFRAGEN_FILE, asked_q_ids)
        flash('Quizfrage gesendet!', 'success')
    return redirect(url_for('index'))

@app.route('/send_umfrage', methods=['POST'])
def send_umfrage_route():
    config = load_config().get('umfrage', {})
    bot_token, channel_id = config.get('token'), config.get('channel_id')
    if not bot_token or not channel_id: return redirect(url_for('index'))
    all_p = load_json(UMFRAGEN_FILE, [])
    asked_p_ids = load_json(GESTELLTE_UMFRAGEN_FILE, [])
    for i, p in enumerate(all_p):
        if 'id' not in p: p['id'] = i
    available = [p for p in all_p if p.get('id') not in asked_p_ids]
    if not available:
        asked_p_ids = []
        save_json(GESTELLTE_UMFRAGEN_FILE, asked_p_ids)
        available = all_p
    if not available: return redirect(url_for('index'))
    poll = random.choice(available)
    success, error = asyncio.run(send_telegram_poll(bot_token, channel_id, poll.get('frage'), poll.get('optionen'), 'regular', is_anonymous=False))
    if success:
        asked_p_ids.append(poll['id'])
        save_json(GESTELLTE_UMFRAGEN_FILE, asked_p_ids)
        flash('Umfrage gesendet!', 'success')
    return redirect(url_for('index'))

@app.route('/save_settings', methods=['POST'])
def handle_settings():
    config = load_config()
    form = request.form
    config_type = form.get('config_type')
    if config_type not in config: return redirect(url_for('index'))
    action = form.get('action')
    if action == 'save_settings':
        config[config_type].update({'token': form.get('token', '').strip(), 'channel_id': form.get('channel_id', '').strip(), 'time': form.get('time', '12:00')})
        flash('Gespeichert.', 'success')
    save_json(CONFIG_FILE, config)
    return redirect(url_for('index'))


# --- NEUE WEB ROUTEN (für Outfit-Bot) ---

@app.route("/outfit-bot/dashboard")
def outfit_bot_dashboard():
    try:
        with open('src/outfit_bot_dashboard.html', 'r', encoding='utf-8') as f: template_content = f.read()
        
        bot_config = load_json(OUTFIT_BOT_CONFIG_FILE, {})
        is_running = is_outfit_bot_running()
        logs = get_outfit_bot_logs(30)
        
        return render_template_string(
            template_content, 
            config=bot_config, 
            is_running=is_running,
            logs=logs
        )
    except FileNotFoundError: return "Fehler: Dashboard-Template nicht gefunden.", 404

@app.route("/outfit-bot/start", methods=['POST'])
def outfit_bot_start():
    success, msg = start_outfit_bot()
    if success: flash(msg, "success")
    else: flash(msg, "danger")
    return redirect(url_for('outfit_bot_dashboard'))

@app.route("/outfit-bot/stop", methods=['POST'])
def outfit_bot_stop():
    success, msg = stop_outfit_bot()
    if success: flash(msg, "success")
    else: flash(msg, "danger")
    return redirect(url_for('outfit_bot_dashboard'))

@app.route("/outfit-bot/save-config", methods=['POST'])
def outfit_bot_save_config():
    config = load_json(OUTFIT_BOT_CONFIG_FILE, {})
    form = request.form
    config.update({
        'BOT_TOKEN': form.get('BOT_TOKEN', '').strip(),
        'CHAT_ID': form.get('CHAT_ID', '').strip(),
        'POST_TIME': form.get('POST_TIME', '18:00'),
        'WINNER_TIME': form.get('WINNER_TIME', '22:00'),
        'AUTO_POST_ENABLED': form.get('AUTO_POST_ENABLED') == 'true'
    })
    admin_ids_str = form.get('ADMIN_USER_IDS', '')
    config['ADMIN_USER_IDS'] = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip().isdigit()]
    save_json(OUTFIT_BOT_CONFIG_FILE, config)
    flash("Outfit-Bot Konfiguration gespeichert!", "success")
    return redirect(url_for('outfit_bot_dashboard'))

def trigger_bot_command(command_name):
    with open(f"command_{command_name}.tmp", 'w') as f: f.write('trigger')

@app.route("/outfit-bot/start-contest", methods=['POST'])
def outfit_bot_start_contest():
    if not is_outfit_bot_running():
        flash("Bot läuft nicht! Bitte erst starten.", "danger")
    else:
        trigger_bot_command('start_contest')
        flash("Befehl 'Wettbewerb starten' gesendet.", "info")
    return redirect(url_for('outfit_bot_dashboard'))

@app.route("/outfit-bot/announce-winner", methods=['POST'])
def outfit_bot_announce_winner():
    if not is_outfit_bot_running():
        flash("Bot läuft nicht! Bitte erst starten.", "danger")
    else:
        trigger_bot_command('announce_winner')
        flash("Befehl 'Gewinner auslosen' gesendet.", "info")
    return redirect(url_for('outfit_bot_dashboard'))

# --- Hintergrundprozesse ---
def start_background_processes():
    # Wir starten den Bot beim App-Start automatisch (wie gewünscht), aber mit der neuen start-Funktion
    start_outfit_bot()

def shutdown_background_processes():
    # Stelle sicher, dass der Outfit-Bot sauber beendet wird, wenn die Flask-App herunterfährt
    stop_outfit_bot()

# === ANWENDUNGSSTART ===
if __name__ == '__main__':
    atexit.register(shutdown_background_processes)
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true': # Startet den Bot nur einmal im Hauptprozess
         start_background_processes() 

    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=True)
