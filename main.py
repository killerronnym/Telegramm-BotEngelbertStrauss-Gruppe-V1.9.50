import os
import random
import json
import asyncio
import logging
import atexit
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for
import telegram
from telegram.error import TelegramError
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

app = Flask(__name__, template_folder='src')
app.secret_key = os.urandom(24)

# --- Logging Konfiguration ---
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# --- Dateinamen ---
CONFIG_FILE = 'config.json'
QUIZFRAGEN_FILE = 'quizfragen.json'
GESTELLTE_QUIZFRAGEN_FILE = 'gestellte_quizfragen.json'
UMFRAGEN_FILE = 'umfragen.json'
GESTELLTE_UMFRAGEN_FILE = 'gestellte_umfragen.json'

# --- Hilfsfunktionen für JSON ---
def load_json(file_path, default_data):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        app.logger.error(f"Fehler beim Dekodieren der JSON-Datei: {file_path}")
        return default_data

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_config():
    default_config = {
        "quiz": {"token": "", "channel_id": "", "daily_enabled": False, "time": "18:00"},
        "umfrage": {"token": "", "channel_id": "", "daily_enabled": False, "time": "20:00"}
    }
    config = load_json(CONFIG_FILE, default_config)
    config.setdefault('quiz', default_config['quiz'])
    config.setdefault('umfrage', default_config['umfrage'])
    return config

def save_config(config):
    save_json(CONFIG_FILE, config)

# --- Routen ---
@app.route("/")
def index():
    return render_template('index.html', config=load_config())

@app.route('/save_settings', methods=['POST'])
def handle_settings():
    config_type = request.form.get('config_type')
    if config_type not in ['quiz', 'umfrage']:
        flash('Ungültiger Konfigurationstyp.', 'danger')
        return redirect(url_for('index'))

    config = load_config()
    action = request.form.get('action')

    new_token = request.form.get('token', '').strip()
    if new_token:
        config[config_type]['token'] = new_token

    new_channel_id = request.form.get('channel_id', '').strip()
    if new_channel_id:
        config[config_type]['channel_id'] = new_channel_id

    new_time = request.form.get('time')
    if new_time:
        config[config_type]['time'] = new_time

    if action == 'activate_daily':
        config[config_type]['daily_enabled'] = True
        flash(f'Tägliche {config_type.capitalize()}-Posts aktiviert!', 'success')
    elif action == 'deactivate_daily':
        config[config_type]['daily_enabled'] = False
        flash(f'Tägliche {config_type.capitalize()}-Posts deaktiviert!', 'warning')
    else:
        flash(f'{config_type.capitalize()}-Einstellungen erfolgreich gespeichert!', 'success')

    save_config(config)
    return redirect(url_for('index'))

# --- Telegram Sende-Funktionen & Logik ---
async def send_telegram_poll(token, chat_id, frage_obj, poll_type):
    bot = telegram.Bot(token=token)
    params = {'chat_id': chat_id, 'question': frage_obj['frage'], 'options': frage_obj['optionen'], 'is_anonymous': (poll_type != 'quiz')}
    if poll_type == 'quiz':
        params.update({'type': 'quiz', 'correct_option_id': frage_obj['antwort']})
    await bot.send_poll(**params)

def handle_sending(config_type, is_manual_request=True):
    config = load_config()
    bot_token = config[config_type].get('token')
    channel_id = config[config_type].get('channel_id')
    
    flash_subject = "Quizfrage" if config_type == 'quiz' else "Umfrage"
    file_path = QUIZFRAGEN_FILE if config_type == 'quiz' else UMFRAGEN_FILE
    gestellte_file_path = GESTELLTE_QUIZFRAGEN_FILE if config_type == 'quiz' else GESTELLTE_UMFRAGEN_FILE

    app.logger.info(f"Versuch, eine '{flash_subject}' an Channel {channel_id} zu senden. Manueller Aufruf: {is_manual_request}")

    if not bot_token or not channel_id:
        msg = f'Fehler: Bot Token oder Channel ID für {flash_subject} fehlt.'
        if is_manual_request: flash(msg, 'danger')
        app.logger.error(f"Senden fehlgeschlagen: {msg}")
        return redirect(url_for('index')) if is_manual_request else None
        
    verfuegbare_items = load_json(file_path, [])
    if not verfuegbare_items:
        msg = f'Keine neuen {flash_subject} mehr verfügbar!'
        if is_manual_request: flash(msg, 'warning')
        app.logger.warning(f"{msg} in {file_path}.")
        return redirect(url_for('index')) if is_manual_request else None

    item_obj = random.choice(verfuegbare_items)

    try:
        asyncio.run(send_telegram_poll(bot_token, channel_id, item_obj, 'quiz' if config_type == 'quiz' else 'regular'))
        msg = f'{flash_subject.capitalize()} "{item_obj["frage"]}" wurde erfolgreich gesendet!'
        if is_manual_request: flash(msg, 'success')
        app.logger.info(msg)
        
        verfuegbare_items.remove(item_obj)
        gestellte_items = load_json(gestellte_file_path, [])
        gestellte_items.append(item_obj)
        save_json(file_path, verfuegbare_items)
        save_json(gestellte_file_path, gestellte_items)

    except TelegramError as e:
        msg = f'Telegram-Fehler ({flash_subject}): {e.message}.'
        if is_manual_request: flash(msg, 'danger')
        app.logger.exception(f"Telegram API Fehler: {msg}")
    except Exception as e:
        msg = f'Ein unerwarteter Fehler ({flash_subject}): {e}'
        if is_manual_request: flash(msg, 'danger')
        app.logger.exception(f"Unerwarteter Fehler: {msg}")

    return redirect(url_for('index')) if is_manual_request else None

@app.route('/send_quizfrage', methods=['POST'])
def send_quizfrage_route():
    return handle_sending('quiz')

@app.route('/send_umfrage', methods=['POST'])
def send_umfrage_route():
    return handle_sending('umfrage')

# --- Scheduler Job ---
def scheduled_job():
    """Wird jede Minute vom Scheduler aufgerufen und berücksichtigt die deutsche Zeitzone."""
    german_tz = pytz.timezone('Europe/Berlin')
    now_german = datetime.now(german_tz).strftime('%H:%M')
    
    app.logger.info(f"Scheduler prüft auf Aufgaben. Aktuelle deutsche Zeit: {now_german}")
    
    config = load_config()

    for task_type in ['quiz', 'umfrage']:
        task_config = config[task_type]
        if task_config.get('daily_enabled') and task_config.get('time') == now_german:
            app.logger.info(f"Geplante Aufgabe '{task_type}' wird ausgeführt um {now_german} deutscher Zeit.")
            with app.app_context():
                handle_sending(task_type, is_manual_request=False)

# --- Scheduler Initialisierung ---
# Verhindert, dass der Scheduler im Haupt-("Wach"-)Prozess des Debug-Servers gestartet wird
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(scheduled_job, 'cron', minute='*')
    scheduler.start()
    # Stellt sicher, dass der Scheduler sauber heruntergefahren wird
    atexit.register(lambda: scheduler.shutdown())
