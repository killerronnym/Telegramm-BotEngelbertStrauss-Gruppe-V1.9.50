
import logging
import os
import json
import re
from datetime import datetime, timedelta
from telegram import Update, ChatPermissions
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Konfiguration & Pfade ---
# Pfade relativ zum Ausführungsort
CONFIG_FILE = 'id_finder_config.json'
COMMAND_LOG_FILE = 'id_finder_command.log'

# Data Ordner liegt eine Ebene höher
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

MODERATION_DATA_FILE = os.path.join(DATA_DIR, "moderation_data.json")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Fehler beim Laden der Konfiguration: {e}")
        return {}

def load_moderation_data():
    if not os.path.exists(MODERATION_DATA_FILE):
        return {}
    try:
        with open(MODERATION_DATA_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Fehler beim Laden der Moderationsdaten: {e}")
        return {}

def save_moderation_data(data):
    try:
        with open(MODERATION_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Moderationsdaten: {e}")

def log_command(user_id, user_name, command, target_id=None, details=None):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_entry = f"[{timestamp}] User: {user_name} ({user_id}) | Cmd: {command} | Target: {target_id} | Details: {details}\n"
    with open(COMMAND_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry)

# --- Hilfsfunktionen ---
def get_reply_parameters(config, update: Update):
    """Ermittelt, wohin eine Antwortnachricht gesendet werden soll."""
    log_topic_id = config.get('log_topic_id')
    main_group_id = config.get('main_group_id')
    
    # Konvertiere IDs zu int, falls sie Strings sind
    if log_topic_id:
        try: log_topic_id = int(log_topic_id)
        except: log_topic_id = None
    if main_group_id:
        try: main_group_id = int(main_group_id)
        except: main_group_id = None

    if log_topic_id and main_group_id:
        return {
            "chat_id": main_group_id,
            "message_thread_id": log_topic_id
        }
    else:
        return {
            "chat_id": update.effective_chat.id,
            "message_thread_id": update.effective_message.message_thread_id if update.effective_message else None
        }

async def get_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Extrahiert den Zielnutzer aus der Nachricht (Reply oder Argument)."""
    target_user = None
    args = list(context.args) # Create a mutable copy
    
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif args:
        try:
            user_id = int(args[0])
            try:
                chat_id = update.effective_chat.id
                member = await context.bot.get_chat_member(chat_id, user_id)
                target_user = member.user
                args = args[1:] # Argument entfernen, da verarbeitet
            except Exception:
                pass
        except ValueError:
            pass # Erstes Argument war keine ID
            
    return target_user, args

# --- Befehls-Handler ---

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat = update.effective_chat
    topic_id = update.message.message_thread_id
    
    response = f"👤 Deine ID: `{user.id}`\n"
    response += f"💬 Chat ID: `{chat.id}`\n"
    if topic_id:
        response += f"🧵 Topic ID: `{topic_id}`"
        
    # Wenn auf eine Nachricht geantwortet wird, auch deren Details anzeigen
    if update.message.reply_to_message:
        original_msg = update.message.reply_to_message
        original_user = original_msg.from_user
        response += f"\n\n👇 **Ziel-Nachricht** 👇\n"
        response += f"👤 User ID: `{original_user.id}`\n"
        response += f"📄 Message ID: `{original_msg.message_id}`"

    await update.message.reply_text(response, parse_mode='Markdown')
    log_command(user.id, user.full_name, "/id")

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    response = f"💬 Die ID dieses Chats ist: `{chat.id}`"
    if update.effective_message.message_thread_id:
        response += f"\n🧵 Topic ID: `{update.effective_message.message_thread_id}`"
    await update.message.reply_text(response, parse_mode='Markdown')
    log_command(update.effective_user.id, update.effective_user.full_name, "/ChatID")

async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    response = f"👤 Deine User ID ist: `{user.id}`"
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        response += f"\n\n👇 **Ziel-Nachricht User ID** 👇\n👤 User ID: `{target_user.id}`"
    await update.message.reply_text(response, parse_mode='Markdown')
    log_command(user.id, user.full_name, "/UserID")


async def warn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user, args = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text("Bitte antworte auf eine Nachricht oder gib eine User-ID an, um jemanden zu verwarnen.")
        return

    reason = " ".join(args) if args else "Kein Grund angegeben"
    
    data = load_moderation_data()
    user_id_str = str(target_user.id)
    
    if user_id_str not in data:
        data[user_id_str] = {"warns": 0, "history": []}
    
    data[user_id_str]["warns"] += 1
    data[user_id_str]["history"].append({
        "type": "warn",
        "reason": reason,
        "date": datetime.now().isoformat(),
        "by": update.effective_user.id
    })
    
    save_moderation_data(data)
    
    log_command(update.effective_user.id, update.effective_user.full_name, "/warn", target_user.id, reason)
    
    config = load_config()
    reply_params = get_reply_parameters(config, update)
    
    msg_text = f"⚠️ Benutzer {target_user.full_name} (`{target_user.id}`) wurde verwarnt.\nGrund: {reason}\nAnzahl Verwarnungen: {data[user_id_str]['warns']}"
    
    try:
        await context.bot.send_message(text=msg_text, parse_mode='Markdown', **reply_params)
    except Exception as e:
        logger.error(f"Konnte Verwarnung nicht senden: {e}")
        await update.message.reply_text(msg_text, parse_mode='Markdown')

async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user, args = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text("Zielnutzer nicht gefunden.")
        return

    reason = " ".join(args) if args else "Kein Grund angegeben"
    
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
        await context.bot.unban_chat_member(update.effective_chat.id, target_user.id) # Unban immediately to allow rejoin (Kick)
        
        log_command(update.effective_user.id, update.effective_user.full_name, "/kick", target_user.id, reason)
        
        config = load_config()
        reply_params = get_reply_parameters(config, update)
        msg_text = f"👢 Benutzer {target_user.full_name} (`{target_user.id}`) wurde gekickt.\nGrund: {reason}"
        
        try:
            await context.bot.send_message(text=msg_text, parse_mode='Markdown', **reply_params)
        except:
            await update.message.reply_text(msg_text, parse_mode='Markdown')
            
    except TelegramError as e:
        await update.message.reply_text(f"Fehler beim Kicken: {e}")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user, args = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text("Zielnutzer nicht gefunden.")
        return

    reason = " ".join(args) if args else "Kein Grund angegeben"
    
    try:
        await context.bot.ban_chat_member(update.effective_chat.id, target_user.id)
        
        log_command(update.effective_user.id, update.effective_user.full_name, "/ban", target_user.id, reason)
        
        config = load_config()
        reply_params = get_reply_parameters(config, update)
        msg_text = f"🔨 Benutzer {target_user.full_name} (`{target_user.id}`) wurde gebannt.\nGrund: {reason}"
        
        try:
            await context.bot.send_message(text=msg_text, parse_mode='Markdown', **reply_params)
        except:
            await update.message.reply_text(msg_text, parse_mode='Markdown')

    except TelegramError as e:
        await update.message.reply_text(f"Fehler beim Bannen: {e}")

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user, args = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text("Bitte antworte auf eine Nachricht oder gib eine User-ID an, um jemanden stummzuschalten.")
        return

    duration_str = None
    reason = "Kein Grund angegeben"

    if args:
        # Check if the first arg is a duration (e.g., "1h", "30m", "7d")
        duration_match = re.match(r'(\d+)([hmd])', args[0])
        if duration_match:
            amount = int(duration_match.group(1))
            unit = duration_match.group(2)
            if unit == 'h':
                duration = timedelta(hours=amount)
            elif unit == 'm':
                duration = timedelta(minutes=amount)
            elif unit == 'd':
                duration = timedelta(days=amount)
            duration_str = args.pop(0) # Remove duration from args
            reason = " ".join(args) if args else "Kein Grund angegeben"
        else:
            reason = " ".join(args)

    if not duration_str: # Default to 1 hour if no duration was specified
        duration = timedelta(hours=1)
        duration_str = "1h"

    until_date = datetime.now() + duration
    
    try:
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        
        log_command(update.effective_user.id, update.effective_user.full_name, "/mute", target_user.id, f"{duration_str} {reason}")
        
        config = load_config()
        reply_params = get_reply_parameters(config, update)
        msg_text = (
            f"🤐 Benutzer {target_user.full_name} (`{target_user.id}`) wurde für {duration_str} stummgeschaltet."
            f"\nGrund: {reason}\nEntbannt am: {until_date.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        try:
            await context.bot.send_message(text=msg_text, parse_mode='Markdown', **reply_params)
        except Exception as e:
            logger.error(f"Konnte Mute-Nachricht nicht senden: {e}")
            await update.message.reply_text(msg_text, parse_mode='Markdown')

    except TelegramError as e:
        await update.message.reply_text(f"Fehler beim Muten: {e}")


# --- Bot Start ---
if __name__ == "__main__":
    config = load_config()
    token = config.get("bot_token")
    
    if not token:
        logger.info("ID Finder Bot ist deaktiviert oder Token fehlt.")
    else:
        app = ApplicationBuilder().token(token).build()
        
        app.add_handler(CommandHandler("id", get_id))
        app.add_handler(CommandHandler("ChatID", get_chat_id))
        app.add_handler(CommandHandler("UserID", get_user_id))
        app.add_handler(CommandHandler("warn", warn_user))
        app.add_handler(CommandHandler("kick", kick_user))
        app.add_handler(CommandHandler("ban", ban_user))
        app.add_handler(CommandHandler("mute", mute_user))
        
        logger.info("🆔 ID Finder Bot läuft...")
        app.run_polling()
