import logging
import os
import json
import sys
import asyncio
from datetime import datetime
from typing import Dict, Any, List

# --- Paths ---
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BOT_DIR))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

CONFIG_FILE = os.path.join(BOT_DIR, "id_finder_config.json")
ACTIVITY_LOG_FILE = os.path.join(DATA_DIR, "activity_log.jsonl")
USER_REGISTRY_FILE = os.path.join(DATA_DIR, "user_registry.json")
USER_MESSAGE_DIR = os.path.join(DATA_DIR, "user_messages")
BROADCAST_DATA_FILE = os.path.join(DATA_DIR, "scheduled_broadcasts.json")
UPLOAD_DIR = os.path.join(DATA_DIR, "broadcast_uploads")
os.makedirs(USER_MESSAGE_DIR, exist_ok=True)

# --- Logging ---
LOG_FILE = os.path.join(BOT_DIR, "id_finder_bot.log")
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8'), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

try:
    from telegram import Update
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, Application
except ImportError:
    logger.error("Erforderliche Bibliothek 'python-telegram-bot' nicht gefunden! Bitte stellen Sie sicher, dass Sie die virtuelle Umgebung (.venv) verwenden.")
    sys.exit(1)

# --- Globals & Locks ---
_FILE_LOCK = asyncio.Lock()
_USER_REGISTRY_CACHE = {"users": {}}
_USER_REGISTRY_DIRTY = False
CONFIG_CACHE = {}

# --- Helpers ---
def _load_json_sync(path):
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

async def load_json_async(path, default=None):
    if not os.path.exists(path): return default if default is not None else {}
    async with _FILE_LOCK:
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _load_json_sync, path)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Fehler beim Laden von {path}: {e}")
            return default if default is not None else {}

def _save_json_sync(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def save_json_async(path, data):
    async with _FILE_LOCK:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _save_json_sync, path, data)
        except IOError as e:
            logger.error(f"Fehler beim Speichern von {path}: {e}")

def _append_file_sync(path, content):
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)

async def append_jsonl_async(path: str, obj: Dict[str, Any]):
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    async with _FILE_LOCK:
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _append_file_sync, path, line)
        except IOError as e:
            logger.error(f"Fehler beim Schreiben in JSONL {path}: {e}")
            raise

# --- Config Management ---
def validate_config(cfg: Dict[str, Any]) -> bool:
    required_keys = {
        "bot_token": str,
        "main_group_id": int,
        "message_logging_enabled": bool
    }
    for key, key_type in required_keys.items():
        if key not in cfg:
            logger.critical(f"FEHLER: Fehlender Schlüssel in der Konfiguration: '{key}'")
            return False
        if not isinstance(cfg[key], key_type):
            logger.critical(f"FEHLER: Falscher Datentyp für '{key}'. Erwartet: {key_type.__name__}, gefunden: {type(cfg[key]).__name__}")
            return False
    return True

# --- User Registry Cache ---
async def load_user_registry():
    global _USER_REGISTRY_CACHE
    logger.info("Lade Benutzer-Registry in den Cache...")
    data = await load_json_async(USER_REGISTRY_FILE, {"users": {}})
    if isinstance(data, dict) and "users" in data:
        _USER_REGISTRY_CACHE = data
    else:
        logger.warning("Benutzer-Registry ist korrupt oder leer. Starte mit leerem Cache.")
        _USER_REGISTRY_CACHE = {"users": {}}


async def persist_user_registry(context: ContextTypes.DEFAULT_TYPE = None):
    global _USER_REGISTRY_DIRTY
    if _USER_REGISTRY_DIRTY:
        logger.info("Speichere Änderungen der Benutzer-Registry...")
        await save_json_async(USER_REGISTRY_FILE, _USER_REGISTRY_CACHE)
        _USER_REGISTRY_DIRTY = False
        logger.info("Speichern der Benutzer-Registry abgeschlossen.")

def schedule_registry_persistence(app: Application):
    if app.job_queue:
        app.job_queue.run_repeating(persist_user_registry, interval=60, first=60)
        logger.info("Automatisches Speichern der Benutzer-Registry alle 60s geplant.")

# --- Broadcast Engine ---
async def update_broadcast_status(broadcast_id: str, new_status: str, sent_at: str = None, error_msg: str = None):
    broadcasts: List[Dict[str, Any]] = await load_json_async(BROADCAST_DATA_FILE, [])
    found = False
    for i, b in enumerate(broadcasts):
        if b.get("id") == broadcast_id:
            b["status"] = new_status
            if sent_at:
                b["sent_at"] = sent_at
            if error_msg:
                b["error_msg"] = error_msg
            broadcasts[i] = b
            found = True
            break
    if found:
        await save_json_async(BROADCAST_DATA_FILE, broadcasts)

async def send_scheduled_broadcast(context: ContextTypes.DEFAULT_TYPE, broadcast_id: str):
    logger.info(f"Sende geplanten Broadcast {broadcast_id}...")
    broadcasts: List[Dict[str, Any]] = await load_json_async(BROADCAST_DATA_FILE, [])
    broadcast_item = next((b for b in broadcasts if b.get("id") == broadcast_id), None)

    if not broadcast_item:
        return

    main_group = CONFIG_CACHE.get("main_group_id")
    if not main_group:
        await update_broadcast_status(broadcast_id, "error", error_msg="Main group ID not configured.")
        return

    if broadcast_item.get("status") == "sent":
        return

    try:
        thread_id = int(broadcast_item["topic_id"]) if str(broadcast_item.get("topic_id")).isdigit() else None
        
        await context.bot.send_message(
            chat_id=main_group,
            text=broadcast_item["text"],
            message_thread_id=thread_id,
            disable_notification=broadcast_item.get("silent_send", False)
        )
        
        await update_broadcast_status(broadcast_id, "sent", sent_at=datetime.now().isoformat())
        logger.info(f"Broadcast {broadcast_id} erfolgreich gesendet.")

    except Exception as e:
        logger.error(f"Fehler beim Senden von Broadcast {broadcast_id}: {e}")
        await update_broadcast_status(broadcast_id, "error", error_msg=str(e))


async def check_and_schedule_broadcasts(context: ContextTypes.DEFAULT_TYPE):
    broadcasts: List[Dict[str, Any]] = await load_json_async(BROADCAST_DATA_FILE, [])
    current_jobs = context.job_queue.get_jobs_by_name("broadcast_job_")
    scheduled_broadcast_ids = {job.name.replace("broadcast_job_", "") for job in current_jobs}

    for b in broadcasts:
        broadcast_id = b.get("id")
        if not broadcast_id or b.get("status") in ["sent", "error"]:
            continue

        try:
            scheduled_at_str = b.get("scheduled_at")
            now = datetime.now()

            if scheduled_at_str:
                scheduled_dt = datetime.fromisoformat(scheduled_at_str)
                if scheduled_dt > now:
                    if broadcast_id not in scheduled_broadcast_ids:
                        context.job_queue.run_once(
                            lambda ctx, bid=broadcast_id: send_scheduled_broadcast(ctx, bid),
                            when=scheduled_dt,
                            name=f"broadcast_job_{broadcast_id}"
                        )
                        await update_broadcast_status(broadcast_id, "scheduled")
                else:
                    await send_scheduled_broadcast(context, broadcast_id)
            else:
                await send_scheduled_broadcast(context, broadcast_id)
        except Exception as e:
            logger.error(f"Fehler bei Broadcast-Planung {broadcast_id}: {e}")

# --- Activity Tracking ---
async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _USER_REGISTRY_CACHE, _USER_REGISTRY_DIRTY
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not all([msg, user, chat]): return
    if not CONFIG_CACHE.get("message_logging_enabled", True): return

    now_str = datetime.now().isoformat()
    uid = str(user.id)

    try:
        entry = _USER_REGISTRY_CACHE["users"].get(uid, {})
        if not entry or entry.get("username") != user.username or entry.get("full_name") != user.full_name:
            entry.update({"username": user.username, "full_name": user.full_name})
            _USER_REGISTRY_DIRTY = True
        entry["last_seen"] = now_str
        if "first_seen" not in entry: entry["first_seen"] = now_str
        _USER_REGISTRY_CACHE["users"][uid] = entry
    except Exception as e:
        logger.error(f"Registry-Update Fehler: {e}")
    
    # Prepare Log Data
    has_media = False
    media_kind = None
    if msg.photo:
        has_media = True
        media_kind = "photo"
    elif msg.video:
        has_media = True
        media_kind = "video"
    elif msg.document:
        has_media = True
        media_kind = "document"
    elif msg.sticker:
        has_media = True
        media_kind = "sticker"
    elif msg.voice:
        has_media = True
        media_kind = "voice"
    elif msg.audio:
        has_media = True
        media_kind = "audio"
    elif msg.animation:
        has_media = True
        media_kind = "animation"

    msg_type = "text" if msg.text else (media_kind if media_kind else "unknown")

    log_entry = {
        "ts": now_str,
        "chat_id": chat.id,
        "chat_type": chat.type,
        "chat_title": chat.title,
        "thread_id": msg.message_thread_id,
        "message_id": msg.message_id,
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "text": msg.text or msg.caption or "",
        "msg_type": msg_type,
        "has_media": has_media,
        "media_kind": media_kind,
        "is_command": msg.text.startswith("/") if msg.text else False
    }

    await append_jsonl_async(ACTIVITY_LOG_FILE, log_entry)
    await append_jsonl_async(os.path.join(USER_MESSAGE_DIR, f"{uid}.jsonl"), log_entry)

# --- Commands ---
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👤 *Benutzer-ID:* `{update.effective_user.id}`\n"
        f"💬 *Chat-ID:* `{update.effective_chat.id}`\n"
        f"🏷️ *Topic-ID:* `{update.effective_message.message_thread_id or 'Kein Topic'}`",
        parse_mode="Markdown"
    )

async def shutdown(app: Application):
    logger.info("Bot wird heruntergefahren...")
    await persist_user_registry()

def main():
    if not os.path.exists(CONFIG_FILE):
        logger.critical("Konfigurationsdatei fehlt!")
        sys.exit(1)
        
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    
    if not validate_config(config):
        sys.exit(1)
        
    global CONFIG_CACHE
    CONFIG_CACHE = config

    app = ApplicationBuilder().token(config["bot_token"]).post_shutdown(shutdown).build()
    
    loop = asyncio.get_event_loop()
    loop.run_until_complete(load_user_registry())

    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_activity))
    app.add_handler(CommandHandler("id", get_id))

    schedule_registry_persistence(app)
    if app.job_queue:
        app.job_queue.run_repeating(check_and_schedule_broadcasts, interval=300, first=1)

    logger.info("ID-Finder Bot startet...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
