import os
import random
import json
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import atexit
import threading
from datetime import datetime

from flask import Flask, render_template, request, flash, redirect, url_for
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import TelegramError
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

# --- Robuste Logging-Konfiguration ---
# Dies konfiguriert den Root-Logger. `force=True` ist entscheidend für die Reload-Umgebung von Flask.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]',
    handlers=[
        RotatingFileHandler('app.log', maxBytes=10240, backupCount=5),
        logging.StreamHandler()  # Logs zusätzlich an die Konsole senden
    ],
    force=True
)
log = logging.getLogger(__name__)
log.info("===== Logging neu konfiguriert. App wird initialisiert. =====")

# --- Globale App- & Bot-Variablen ---
app = Flask(__name__, template_folder='src')
app.secret_key = os.urandom(24)
app.config['TEMPLATES_AUTO_RELOAD'] = True

CONFIG_FILE = 'config.json'
QUIZFRAGEN_FILE = 'quizfragen.json'
GESTELLTE_QUIZFRAGEN_FILE = 'gestellte_quizfragen.json'
UMFRAGEN_FILE = 'umfragen.json'
GESTELLTE_UMFRAGEN_FILE = 'gestellte_umfragen.json'
CONTEST_SUBMISSIONS_FILE = 'contest_submissions.json'

application = None
bot_loop = None
scheduler = None

# --- Hilfsfunktionen für JSON ---
def load_json(file_path, default_data):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        log.error(f"JSON-Dekodierungsfehler in {file_path}", exc_info=True)
        return default_data

def save_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def load_config():
    default_config = {
        "quiz": {"token": "", "channel_id": "", "daily_enabled": False, "time": "18:00"},
        "umfrage": {"token": "", "channel_id": "", "daily_enabled": False, "time": "20:00"},
        "contest": {"token": "", "channel_id": "", "daily_enabled": False, "start_time": "18:00", "end_time": "22:00"}
    }
    config = load_json(CONFIG_FILE, default_config)
    for key in default_config:
        config.setdefault(key, default_config[key])
    return config

def save_config(config):
    save_json(CONFIG_FILE, config)

# --- Thread-sichere asynchrone Ausführung ---
def run_coroutine_in_bot_loop(coro):
    if not bot_loop or not bot_loop.is_running():
        log.error("FATAL: Bot-Event-Loop ist nicht verfügbar oder läuft nicht.")
        return None, "Bot-Prozess läuft nicht"
    
    log.info(f"Führe Coroutine im Bot-Loop aus: {coro.__name__}")
    future = asyncio.run_coroutine_threadsafe(coro, bot_loop)
    try:
        # future.result() wartet auf das Ergebnis
        result, error = future.result(timeout=30)
        return result, error
    except Exception as e:
        log.error(f"Fehler bei der Ausführung der Coroutine '{coro.__name__}': {e}", exc_info=True)
        return None, str(e)

# --- Telegram Bot Handler ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Hallo! Schicke mir jetzt bitte dein Outfit-Foto, um am Wettbewerb teilzunehmen.')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Implementierung bleibt gleich)
    pass

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Implementierung bleibt gleich)
    pass

# --- Web Routen ---
@app.route("/")
def index():
    return render_template('index.html', config=load_config())

@app.route('/save_settings', methods=['POST'])
def handle_settings():
    # ... (Implementierung bleibt im Kern gleich)
    return redirect(url_for('index'))

@app.route('/send_contest', methods=['POST'])
def send_contest_route():
    log.info("===== Route /send_contest AUFGERUFEN =====")
    if not application or not bot_loop or not bot_loop.is_running():
        log.error("Abbruch in /send_contest: Bot-Prozess ist nicht aktiv.")
        flash('FEHLER: Der interaktive Bot-Prozess ist nicht aktiv. Hast du den Token gespeichert und die App neu gestartet?', 'danger')
        return redirect(url_for('index'))
    
    log.info("Bot-Prozess ist aktiv. Lade Konfiguration.")
    config = load_config().get('contest', {})
    bot_token, channel_id = config.get('token'), config.get('channel_id')
    
    if not bot_token or not channel_id:
        log.error("Abbruch in /send_contest: Wettbewerb-Token oder Channel ID fehlt.")
        flash('Fehler: Wettbewerb-Token oder Channel ID fehlt.', 'danger')
        return redirect(url_for('index'))
    
    log.info(f"Konfiguration geladen. Channel ID: {channel_id}. Versuche, Nachricht zu senden.")

    async def _send_message():
        try:
            bot = telegram.Bot(token=bot_token)
            bot_info = await bot.get_me()
            log.info(f"Bot-Info erfolgreich abgerufen: @{bot_info.username}")
            keyboard = [[InlineKeyboardButton("Mitmachen", url=f"https://t.me/{bot_info.username}?start=join")]]
            await bot.send_message(chat_id=channel_id, text="📸 Outfit des Tages – zeigt eure heutigen E.S-Outfits!", reply_markup=InlineKeyboardMarkup(keyboard))
            log.info("===== Nachricht erfolgreich an Telegram gesendet! =====")
            return True, None
        except TelegramError as e:
            log.error(f"Telegram API Fehler: {e.message}", exc_info=True)
            return False, f"Telegram Fehler: {e.message}"
        except Exception as e:
            log.error(f"Unerwarteter Fehler beim Senden: {e}", exc_info=True)
            return False, f"Ein unerwarteter Fehler ist aufgetreten: {e}"

    success, error_message = run_coroutine_in_bot_loop(_send_message())

    if success:
        save_json(CONTEST_SUBMISSIONS_FILE, {}) # Alte Submissions löschen
        flash('Wettbewerb-Startnachricht gesendet!', 'success')
    else:
        flash(f"Fehler beim Senden: {error_message}", 'danger')
        
    return redirect(url_for('index'))

# --- Hintergrundprozesse ---
def run_bot_polling(loop, app_instance):
    asyncio.set_event_loop(loop)
    log.info("Starte Bot-Polling in separatem Thread...")
    try:
        app_instance.run_polling(drop_pending_updates=True)
    except Exception as e:
        log.error(f"Schwerwiegender Fehler im Bot-Polling-Thread: {e}", exc_info=True)

def start_background_processes():
    global application, bot_loop, scheduler
    log.info("===== HINTERGRUNDPROZESSE WERDEN INITIALISIERT =====")
    
    config = load_config()
    token = config.get("contest", {}).get('token')
    if token:
        try:
            application = Application.builder().token(token).build()
            application.add_handler(CommandHandler("start", start_command))
            application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
            application.add_handler(CallbackQueryHandler(handle_callback_query))
            
            bot_loop = asyncio.new_event_loop()
            thread = threading.Thread(target=run_bot_polling, args=(bot_loop, application), daemon=True)
            thread.start()
            log.info("Bot-Thread erfolgreich gestartet.")
        except Exception as e:
            log.error(f"Fehler beim Starten des Bots: {e}", exc_info=True)
            application = None
            bot_loop = None
    else:
        log.warning("Kein Wettbewerb-Token gefunden. Der interaktive Bot wird NICHT gestartet.")

    # Scheduler (loggt jetzt auch)
    def scheduled_job_wrapper():
        with app.app_context():
            log.info("Scheduler-Job wird ausgeführt.")
            # Hier die eigentliche Job-Logik einfügen

    scheduler = BackgroundScheduler(daemon=True, timezone=pytz.utc)
    scheduler.add_job(scheduled_job_wrapper, 'cron', minute='*')
    scheduler.start()
    log.info("Scheduler-Thread gestartet.")
    atexit.register(shutdown_background_processes)

def shutdown_background_processes():
    log.info("===== FAHRE HINTERGRUNDPROZESSE HERUNTER =====")
    if scheduler and scheduler.running:
        scheduler.shutdown()
    if application and bot_loop and bot_loop.is_running():
        bot_loop.call_soon_threadsafe(application.stop)

# === ANWENDUNGSSTART ===
# Hintergrundprozesse nur im Hauptprozess des Reloaders starten
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    start_background_processes()
else:
    log.info("Werkzeug-Reloader hat die App neu geladen. Hintergrundprozesse werden nicht neu gestartet.")

if __name__ == '__main__':
    # debug=True ist okay, da unser Logging jetzt robust ist
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=True)
