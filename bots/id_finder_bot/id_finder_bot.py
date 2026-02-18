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
    logger.error("Erforderliche Bibliothek 'python-telegram-bot' nicht gefunden!")
    sys.exit(1)

# --- Globals & Locks ---
_FILE_LOCK = asyncio.Lock()
_USER_REGISTRY_CACHE = {"users": {}}
_USER_REGISTRY_DIRTY = False
CONFIG_CACHE = {}

# --- Helpers ---
def _load_json_sync(path):
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
            raise # Re-raise exception to handle it in caller

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
    """Helper to update the status of a single broadcast item in the file."""
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
    else:
        logger.warning(f"Attempted to update non-existent broadcast ID: {broadcast_id}")


async def send_scheduled_broadcast(context: ContextTypes.DEFAULT_TYPE, broadcast_id: str):
    logger.info(f"Attempting to send scheduled broadcast {broadcast_id}...")
    broadcasts: List[Dict[str, Any]] = await load_json_async(BROADCAST_DATA_FILE, [])
    broadcast_item = next((b for b in broadcasts if b.get("id") == broadcast_id), None)

    if not broadcast_item:
        logger.error(f"Broadcast {broadcast_id} not found in file. Cannot send.")
        return

    main_group = CONFIG_CACHE.get("main_group_id")
    if not main_group:
        logger.error(f"Cannot send broadcast {broadcast_id}: main_group_id not configured.")
        await update_broadcast_status(broadcast_id, "error", error_msg="Main group ID not configured.")
        return

    if broadcast_item.get("status") == "sent":
        logger.info(f"Broadcast {broadcast_id} already sent. Skipping.")
        return # Already sent, avoid re-sending if job somehow triggered again

    try:
        thread_id = int(broadcast_item["topic_id"]) if str(broadcast_item.get("topic_id")).isdigit() else None
        media_path = None
        if broadcast_item.get("media_name"):
            media_path = os.path.join(UPLOAD_DIR, broadcast_item["media_name"])
            if not os.path.exists(media_path):
                logger.error(f"Media file for broadcast {broadcast_id} not found: {media_path}. Marking as error.")
                await update_broadcast_status(broadcast_id, "error", error_msg=f"Media file not found: {media_path}")
                return

        # Placeholder for actual Telegram bot sending logic
        if media_path:
            logger.info(f"Simulating sending media '{media_path}' for broadcast {broadcast_id} to chat {main_group} (topic: {thread_id}).")
            # await context.bot.send_photo(chat_id=main_group, photo=open(media_path, 'rb'), caption=broadcast_item["text"], message_thread_id=thread_id)
        else:
            await context.bot.send_message(
                chat_id=main_group,
                text=broadcast_item["text"],
                message_thread_id=thread_id,
                disable_notification=broadcast_item.get("silent_send", False)
            )
            logger.info(f"Text broadcast {broadcast_id} sent to chat {main_group} (topic: {thread_id}).")

        if broadcast_item.get("pin_message"):
            logger.info(f"Simulating pinning message for broadcast {broadcast_id}.")
            # message_to_pin = await context.bot.send_message(...)
            # await message_to_pin.pin(disable_notification=True)

        await update_broadcast_status(broadcast_id, "sent", sent_at=datetime.now().isoformat())
        logger.info(f"Broadcast {broadcast_id} successfully sent and status updated.")

    except Exception as e:
        logger.error(f"Error during actual sending of broadcast {broadcast_id}: {e}")
        await update_broadcast_status(broadcast_id, "error", error_msg=str(e))


async def check_and_schedule_broadcasts(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Checking and scheduling broadcasts...")
    broadcasts: List[Dict[str, Any]] = await load_json_async(BROADCAST_DATA_FILE, [])
    
    current_jobs = context.job_queue.get_jobs_by_name("broadcast_job_")
    scheduled_broadcast_ids = {job.name.replace("broadcast_job_", "") for job in current_jobs}

    for b in broadcasts:
        broadcast_id = b.get("id")
        if not broadcast_id:
            logger.error(f"Broadcast item without ID found: {b}. Skipping.")
            continue

        if b.get("status") == "sent" or b.get("status") == "error":
            continue

        if broadcast_id in scheduled_broadcast_ids and b.get("status") == "scheduled":
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
                        logger.info(f"Broadcast {broadcast_id} scheduled for {scheduled_dt}.")
                    else:
                        logger.debug(f"Broadcast {broadcast_id} is already scheduled in job queue.")
                else:
                    logger.info(f"Broadcast {broadcast_id} is past due or due now. Sending immediately.")
                    await send_scheduled_broadcast(context, broadcast_id)
            else:
                logger.info(f"Broadcast {broadcast_id} has no schedule. Sending immediately.")
                await send_scheduled_broadcast(context, broadcast_id)

        except (ValueError, TypeError) as e:
            logger.error(f"Invalid scheduled_at format for broadcast {broadcast_id}: {e}. Marking as error.")
            await update_broadcast_status(broadcast_id, "error", error_msg=f"Invalid date format: {e}")
        except Exception as e:
            logger.error(f"Error processing broadcast {broadcast_id} for scheduling/sending: {e}. Marking as error.")
            await update_broadcast_status(broadcast_id, "error", error_msg=str(e))
    
    logger.info("Broadcast scheduling round complete.")

# --- Activity Tracking ---
# Data Redundancy Note:
# Messages are currently logged to both `ACTIVITY_LOG_FILE` (global chronological log)
# and `USER_MESSAGE_DIR/{uid}.jsonl` (individual user message history).
# This creates data redundancy but allows for efficient retrieval of a user's recent messages
# without scanning the entire global activity log, which is beneficial for dashboard performance.
# A more normalized approach would typically involve a database (as suggested in TODO.md).
async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global _USER_REGISTRY_CACHE, _USER_REGISTRY_DIRTY
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not all([msg, user, chat]): return
    
    if not CONFIG_CACHE.get("message_logging_enabled", True): return

    now_str = datetime.now().isoformat()
    uid = str(user.id)

    # 1. Update User Registry (In-Memory)
    try:
        entry = _USER_REGISTRY_CACHE["users"].get(uid, {})
        if not entry or entry.get("username") != user.username or entry.get("full_name") != user.full_name:
            entry.update({"username": user.username, "full_name": user.full_name})
            _USER_REGISTRY_DIRTY = True
        
        entry["last_seen"] = now_str
        if "first_seen" not in entry: entry["first_seen"] = now_str
        
        _USER_REGISTRY_CACHE["users"][uid] = entry
    except Exception as e:
        logger.error(f"Fehler beim Aktualisieren der User Registry für {uid}: {e}")
        # Wenn wir den User nicht registrieren können, sollten wir vielleicht abbrechen?
        # Aber Logging ist wichtiger als Registry-Updates. Wir machen weiter.
    
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
        "msg_type": msg_type,
        "has_media": has_media,
        "media_kind": media_kind,
        "reactions": 0, # Cannot track initial reactions here
        "is_command": msg.text.startswith("/") if msg.text else False
    }

    # 2. Activity Log (Global)
    try:
        await append_jsonl_async(ACTIVITY_LOG_FILE, log_entry)
    except Exception as e:
        logger.error(f"KRITISCH: Konnte Activity Log nicht schreiben. Breche ab, um Inkonsistenz zu vermeiden. Fehler: {e}")
        return # Stop here to avoid having messages in user history but not in activity log

    # 3. User Message History (Individual)
    user_history_file = os.path.join(USER_MESSAGE_DIR, f"{uid}.jsonl")
    try:
        await append_jsonl_async(user_history_file, log_entry)
    except Exception as e:
        logger.error(f"Fehler beim Schreiben der User-History für {uid}: {e}")
        # Activity log was written, so we have at least that.

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

async def main():
    global CONFIG_CACHE
    config = await load_json_async(CONFIG_FILE)
    if not config or not validate_config(config):
        logger.critical("Bot wird aufgrund einer ungültigen oder fehlenden Konfiguration beendet.")
        sys.exit(1)
    CONFIG_CACHE = config
    
    await load_user_registry()

    app = ApplicationBuilder().token(CONFIG_CACHE["bot_token"]).post_shutdown(shutdown).build()
    
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_activity))
    app.add_handler(CommandHandler("id", get_id))

    schedule_registry_persistence(app)
    
    if app.job_queue:
        # Initial check and schedule all pending broadcasts
        await check_and_schedule_broadcasts(app.job_queue.job_queue_context())
        # Periodically re-check for new broadcasts added externally (e.g., via dashboard)
        app.job_queue.run_repeating(check_and_schedule_broadcasts, interval=300, first=60, name="periodic_broadcast_reschedule_check")

    logger.info("ID-Finder Bot gestartet...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot manuell beendet.")
