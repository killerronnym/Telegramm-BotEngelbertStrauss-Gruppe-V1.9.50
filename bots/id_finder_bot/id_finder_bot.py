import logging
import os
import json
import re
import threading
import sys
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8'), logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

try:
    from telegram import Update, Message
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
except ImportError:
    logger.error("Required library 'python-telegram-bot' not found!")
    sys.exit(1)

_FILE_LOCK = threading.Lock()

# --- Helpers ---
def load_json(path, default=None):
    if not os.path.exists(path): return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return default if default is not None else {}

def save_json(path, data):
    with _FILE_LOCK:
        with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=4, ensure_ascii=False)

def _append_jsonl(path: str, obj: Dict[str, Any]):
    try:
        line = json.dumps(obj, ensure_ascii=False)
        with _FILE_LOCK:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception as e:
        logger.error(f"Error writing to JSONL {path}: {e}")

# --- Broadcast Engine ---
async def check_broadcasts(context: ContextTypes.DEFAULT_TYPE):
    broadcasts = load_json(BROADCAST_DATA_FILE, [])
    config = load_json(CONFIG_FILE)
    main_group = config.get("main_group_id")
    
    if not main_group:
        logger.warning("Keine main_group_id in id_finder_config.json konfiguriert! Broadcast kann nicht senden.")
        return

    changed = False
    now = datetime.now()

    for b in broadcasts:
        if b.get("status") != "pending": continue
        
        # Check scheduling
        if b.get("scheduled_at"):
            try:
                sched_time = datetime.fromisoformat(b["scheduled_at"])
                if sched_time > now: continue
            except ValueError:
                # If date format is wrong, try to send immediately or fail
                logger.error(f"Invalid date format for broadcast {b['id']}: {b['scheduled_at']}")
        
        try:
            thread_id = int(b.get("topic_id")) if b.get("topic_id") else None
            text = b.get("text", "")
            media_path = os.path.join(UPLOAD_DIR, b["media_name"]) if b.get("media_name") else None
            silent = b.get("silent_send", False)
            
            sent_msg = None
            
            # Send Logic
            if media_path and os.path.exists(media_path):
                with open(media_path, "rb") as f:
                    if b.get("media_name").lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        sent_msg = await context.bot.send_photo(
                            chat_id=main_group, 
                            photo=f, 
                            caption=text, 
                            message_thread_id=thread_id, 
                            disable_notification=silent
                        )
                    else:
                        sent_msg = await context.bot.send_document(
                            chat_id=main_group, 
                            document=f, 
                            caption=text, 
                            message_thread_id=thread_id, 
                            disable_notification=silent
                        )
            elif text:
                sent_msg = await context.bot.send_message(
                    chat_id=main_group, 
                    text=text, 
                    message_thread_id=thread_id, 
                    disable_notification=silent
                )
            
            # Pin Logic
            if b.get("pin_message") and sent_msg:
                try:
                    await context.bot.pin_chat_message(
                        chat_id=main_group, 
                        message_id=sent_msg.message_id, 
                        disable_notification=True
                    )
                except Exception as e:
                    logger.warning(f"Could not pin message: {e}")
            
            b["status"] = "sent"
            b["sent_at"] = now.isoformat()
            changed = True
            logger.info(f"Broadcast {b['id']} sent successfully to {main_group} (Topic: {thread_id}).")
            
        except Exception as e:
            logger.error(f"Failed to send broadcast {b.get('id')}: {e}")
            b["status"] = "error"
            b["error_msg"] = str(e)
            changed = True

    if changed:
        save_json(BROADCAST_DATA_FILE, broadcasts)

# --- Activity Tracking ---
async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat
    
    if not msg or not user:
        return

    config = load_json(CONFIG_FILE)
    if not config.get("message_logging_enabled", True):
        return

    if config.get("message_logging_groups_only", False) and chat.type not in ["group", "supergroup"]:
        return

    is_cmd = bool(msg.text and msg.text.startswith('/'))
    if is_cmd and config.get("message_logging_ignore_commands", True):
        return

    now_str = datetime.now().isoformat()

    # 1. Update User Registry
    try:
        with _FILE_LOCK:
            reg = {"users": {}}
            if os.path.exists(USER_REGISTRY_FILE):
                try:
                    with open(USER_REGISTRY_FILE, "r", encoding="utf-8") as f:
                        reg = json.load(f)
                except: pass
            
            uid = str(user.id)
            entry = reg["users"].get(uid, {})
            entry.update({
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "last_seen": now_str
            })
            entry.setdefault("first_seen", now_str)
            
            cids = entry.get("chat_ids", [])
            if chat and chat.id not in cids:
                cids.append(chat.id)
            entry["chat_ids"] = cids
            
            reg["users"][uid] = entry
            with open(USER_REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump(reg, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Registry Error: {e}")

    # Media Detection
    media_kind = None
    if msg.photo: media_kind = "photo"
    elif msg.video: media_kind = "video"
    elif msg.sticker: media_kind = "sticker"
    elif msg.document: media_kind = "document"
    elif msg.voice: media_kind = "voice"
    elif msg.audio: media_kind = "audio"
    elif msg.animation: media_kind = "animation"

    # 2. Activity Log (Analytics)
    activity = {
        "ts": now_str,
        "chat_id": chat.id if chat else None,
        "chat_type": chat.type if chat else None,
        "chat_title": chat.title if chat else None,
        "thread_id": msg.message_thread_id,
        "user_id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "msg_type": "text" if not media_kind else media_kind,
        "has_media": media_kind is not None,
        "reactions": 0,
        "is_command": is_cmd
    }
    _append_jsonl(ACTIVITY_LOG_FILE, activity)

    # 3. User History (Verlauf)
    user_log_path = os.path.join(USER_MESSAGE_DIR, f"{user.id}.jsonl")
    history_entry = {
        "ts": now_str,
        "chat_id": chat.id if chat else None,
        "thread_id": msg.message_thread_id,
        "message_id": msg.message_id,
        "text": msg.text or msg.caption or (f"[{media_kind}]" if media_kind else ""),
        "has_media": media_kind is not None,
        "media": {"kind": media_kind} if media_kind else None,
        "msg_type": activity["msg_type"]
    }
    _append_jsonl(user_log_path, history_entry)

# --- Commands ---
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👤 *User ID:* `{update.effective_user.id}`\n"
        f"💬 *Chat ID:* `{update.effective_chat.id}`\n"
        f"🏷️ *Topic ID:* `{update.effective_message.message_thread_id or 'Keins'}`",
        parse_mode="Markdown"
    )

if __name__ == "__main__":
    cfg = load_json(CONFIG_FILE)
    token = cfg.get("bot_token")
    
    if not token:
        logger.error("KEIN BOT TOKEN GEFUNDEN! Bitte id_finder_config.json prüfen.")
        sys.exit(1)

    app = ApplicationBuilder().token(token).build()
    
    # Tracking
    app.add_handler(MessageHandler(filters.ALL, track_activity), group=-1)
    
    # Commands
    app.add_handler(CommandHandler("id", get_id))

    # Broadcast Engine (check every 10 seconds)
    if app.job_queue:
        app.job_queue.run_repeating(check_broadcasts, interval=10, first=5)
        logger.info("Broadcast Engine active.")
    else:
        logger.error("JobQueue not available! Broadcasts will NOT work.")

    logger.info("ID-Finder Bot gestartet...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
