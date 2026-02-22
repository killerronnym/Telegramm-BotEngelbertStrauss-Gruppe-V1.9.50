import logging
import os
import json
import re
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, ChatInviteLink, ChatMember
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    ChatJoinRequestHandler,
    filters,
)

# --- Pfad-Hack für Shared Utils ---
# Wir fügen das Root-Verzeichnis zum Pfad hinzu, um shared_bot_utils zu importieren
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared_bot_utils import get_bot_config, get_env_var

# --- Setup Logging ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'invite_bot.log')

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Dateien & Speicher -----------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
DATA_DIR = Path(os.path.join(PROJECT_ROOT, "data"))
DATA_DIR.mkdir(exist_ok=True, parents=True)

PROFILES_FILE = DATA_DIR / "profiles.json"
USER_INTERACTIONS_LOG_FILE = Path(BASE_DIR) / 'user_interactions.log'

# --- Conversation States ---
FILLING_FORM, CONFIRM_RULES = range(2)

def load_config():
    """Lädt die Konfiguration aus der Datenbank."""
    config = get_bot_config("invite_bot")
    
    # Defaults setzen, falls Felder fehlen
    defaults = {
        "is_enabled": False,
        "main_chat_id": "",
        "topic_id": "",
        "link_ttl_minutes": 15,
        "repost_profile_for_existing_members": True,
        "start_message": "Willkommen! Nutze /letsgo zum Starten.",
        "rules_message": "Bitte bestätige die Regeln mit OK.",
        "blocked_message": "Du wurdest aus dieser Gruppe verbannt und kannst nicht erneut beitreten.",
        "privacy_policy": "Datenschutzerklärung wurde noch nicht konfiguriert.",
        "form_fields": []
    }
    
    # Merge defaults with config
    for key, value in defaults.items():
        if key not in config:
            config[key] = value
            
    # Token Priorität: ENV > DB
    env_token = get_env_var("INVITE_BOT_TOKEN")
    if env_token:
        config["bot_token"] = env_token
        
    return config

def log_user_interaction(user_id: int, username: str, action: str, details: str = ""):
    try:
        with open(USER_INTERACTIONS_LOG_FILE, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            user_info = f"@{username}" if username else f"ID:{user_id}"
            safe_details = str(details).replace('|', ':').replace('\n', ' ')
            f.write(f"[{timestamp}] User: {user_info} | Aktion: {action} | Details: {safe_details}\n")
    except Exception as e:
        logger.error(f"Failed to log interaction: {e}")

def _load_all_profiles():
    if not PROFILES_FILE.exists(): return {}
    try:
        with PROFILES_FILE.open("r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_profile(user_id: int, profile: dict):
    data = _load_all_profiles()
    data[str(user_id)] = profile
    try:
        with PROFILES_FILE.open("w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e: logger.error(f"Fehler beim Speichern der Profile: {e}")

def escape_md(text):
    """Helper to escape MarkdownV2 characters"""
    if not text: return ""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", str(text))

def get_enabled_fields(config):
    return [f for f in config.get("form_fields", []) if f.get("enabled", True)]

async def ask_next_field(update: Update, context: ContextTypes.DEFAULT_TYPE, config: dict):
    fields = get_enabled_fields(config)
    current_idx = context.user_data.get("form_idx", 0)
    
    if current_idx >= len(fields):
        regeln = config.get("rules_message", "Bitte bestätige die Regeln mit OK.")
        try:
            await update.effective_message.reply_text(regeln) 
            await update.effective_message.reply_text("Bitte antworte mit *OK*, um fortzufahren\\.", parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            logger.error(f"Error sending rules: {e}")
            await update.effective_message.reply_text(regeln)
        
        return CONFIRM_RULES

    field = fields[current_idx]
    label = field["label"]
    if not field.get("required"): 
        label += "\n\n_Diese Frage kannst du mit 'nein' überspringen._"
    
    await update.effective_message.reply_text(label) 
    return FILLING_FORM

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    raw_text = config.get("start_message", "👋 *Hey!* \n\n👉 *Schreibe /letsgo, um zu starten!*")
    try:
        await update.message.reply_text(raw_text)
    except Exception as e:
        logger.error(f"Error in welcome: {e}")

async def datenschutz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    text = config.get("privacy_policy", "Keine Datenschutzerklärung hinterlegt.")
    try:
        await update.message.reply_text(text)
    except Exception as e:
        logger.error(f"Error in privacy: {e}")

async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    if not config.get("main_chat_id"):
        await update.message.reply_text("⚠️ Bot ist noch nicht fertig konfiguriert (Gruppen-ID fehlt).")
        return ConversationHandler.END

    # --- Ban Check (Sofortige Prüfung) ---
    try:
        user_id = update.effective_user.id
        group_id = int(config["main_chat_id"])
        chat_member = await context.bot.get_chat_member(group_id, user_id)
        status = getattr(chat_member, "status", str(chat_member.status))
        
        if status in ["kicked", "banned"]:
            blocked_msg = config.get("blocked_message", "Du wurdest aus dieser Gruppe verbannt.")
            await update.message.reply_text(f"⛔ {blocked_msg}")
            return ConversationHandler.END
            
    except Exception as e:
        logger.warning(f"Ban check failed for user {update.effective_user.id}: {e}")
        
    context.user_data["form_idx"] = 0
    context.user_data["answers"] = {
        "telegram_id": update.effective_user.id, 
        "username": update.effective_user.username or "", 
        "first_name": update.effective_user.first_name or ""
    }
    return await ask_next_field(update, context, config)

async def handle_field_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_config()
    fields = get_enabled_fields(config)
    idx = context.user_data.get("form_idx", 0)
    
    if idx >= len(fields): 
        return await ask_next_field(update, context, config)

    field = fields[idx]
    user_input = None
    
    # --- Input Validation ---
    if field["type"] == "photo":
        if update.message.photo:
            user_input = update.message.photo[-1].file_id
        elif not field.get("required") and update.message.text and update.message.text.lower() == "nein":
             user_input = None
        else:
            await update.message.reply_text("⚠️ Bitte sende ein Foto (oder 'nein' zum Überspringen).")
            return FILLING_FORM
            
    elif field["type"] == "number":
        text = update.message.text.strip() if update.message.text else ""
        if text.isdigit():
            user_input = text
            if field.get("min_age"):
                try:
                    min_age = int(field["min_age"])
                    age_val = int(text)
                    if age_val < min_age:
                        error_msg = field.get("min_age_error_msg", f"⚠️ Du musst mindestens {min_age} Jahre alt sein.")
                        await update.message.reply_text(error_msg)
                        return FILLING_FORM
                except ValueError: pass
        elif not field.get("required") and text.lower() == "nein":
            user_input = None
        else:
            await update.message.reply_text("⚠️ Bitte gib eine gültige Zahl ein.")
            return FILLING_FORM
            
    else: # Text / Multiline
        text = update.message.text.strip() if update.message.text else ""
        if not field.get("required") and text.lower() == "nein":
            user_input = None
        elif not text:
             await update.message.reply_text("⚠️ Bitte gib einen Text ein.")
             return FILLING_FORM
        else:
            user_input = text

    context.user_data["answers"][field["id"]] = user_input
    context.user_data["form_idx"] = idx + 1
    
    return await ask_next_field(update, context, config)

async def rules_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text != "ok":
        await update.message.reply_text("Bitte antworte mit *OK*, um fortzufahren\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return CONFIRM_RULES
    
    user_id = update.effective_user.id
    profile = context.user_data["answers"]
    profile["created_at"] = datetime.utcnow().isoformat()
    save_profile(user_id, profile)
    
    config = load_config()
    group_id = int(config["main_chat_id"])
    
    try:
        link = await context.bot.create_chat_invite_link(
            chat_id=group_id, 
            expire_date=datetime.utcnow() + timedelta(minutes=config.get("link_ttl_minutes", 15)), 
            creates_join_request=True
        )
        await update.message.reply_text(
            f"✅ *Vielen Dank\\!* Dein Profil wurde erstellt\\.\n\n"
            f"👇 Klicke hier, um der Gruppe beizutreten:\n{escape_md(link.invite_link)}\n\n"
            f"_Ein Admin oder Bot wird deine Anfrage gleich bestätigen\\._",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        logger.error(f"Link Creation Error: {e}")
        await update.message.reply_text("⚠️ Fehler beim Erstellen des Einladungslinks. Bitte kontaktiere einen Admin.")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Vorgang abgebrochen. Tippe /letsgo um neu zu starten.")
    return ConversationHandler.END

async def post_profile_to_group(context: ContextTypes.DEFAULT_TYPE, profile: dict, config: dict):
    chat_id = int(config["main_chat_id"])
    topic_id = config.get("topic_id")
    if topic_id == "null" or not topic_id: topic_id = None
    
    def esc(t): return escape_md(str(t) if t is not None else "")
    
    user_name = profile.get('first_name') or profile.get('username') or "Unbekannt"
    user_link = f"[{esc(user_name)}](tg://user?id={profile['telegram_id']})"
    
    lines = [f"🎉 *Willkommen in der Gruppe\\!*", f"👤 *User:* {user_link}"]
    photo_id = None
    
    for f in config.get("form_fields", []):
        val = profile.get(f["id"])
        if val is None or val == "": continue
        
        if f["type"] == "photo":
            photo_id = val
        else:
            emoji = f.get("emoji", "🔹")
            display_name = f.get("display_name", f["id"].capitalize())
            lines.append(f"{emoji} *{esc(display_name)}:* {esc(val)}")
    
    now_str = datetime.now().strftime("%d.%m.%Y – %H:%M")
    lines.append(f"🕒 *Beigetreten am:* {esc(now_str)}")
    text = "\n".join(lines)
    
    try:
        if photo_id:
            await context.bot.send_photo(chat_id=chat_id, photo=photo_id, caption=text, parse_mode=ParseMode.MARKDOWN_V2, message_thread_id=topic_id)
        else:
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN_V2, message_thread_id=topic_id)
    except Exception as e:
        logger.error(f"Post profile failed: {e}")

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    user_id = req.from_user.id
    chat_id = req.chat.id
    config = load_config()
    
    if str(chat_id) != str(config.get("main_chat_id")):
        return

    try:
        await context.bot.approve_chat_join_request(chat_id=chat_id, user_id=user_id)
        profiles = _load_all_profiles()
        if str(user_id) in profiles:
            await post_profile_to_group(context, profiles[str(user_id)], config)
    except Exception as e:
        logger.error(f"Join request approval failed: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    config = load_config()
    token = config.get("bot_token")
    
    if not token:
        logger.error("Kein Token konfiguriert! Setze INVITE_BOT_TOKEN Umgebungsvariable oder konfiguriere DB.")
        sys.exit(1)
    
    try:
        app = ApplicationBuilder().token(token).build()
    except Exception as e:
        logger.error(f"Fehler beim Erstellen der App (Token ungültig?): {e}")
        sys.exit(1)
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("letsgo", start_form)],
        states={
            FILLING_FORM: [MessageHandler(filters.ALL & ~filters.COMMAND, handle_field_input)],
            CONFIRM_RULES: [MessageHandler(filters.TEXT & ~filters.COMMAND, rules_confirmed)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(CommandHandler("start", welcome))
    app.add_handler(CommandHandler("datenschutz", datenschutz))
    app.add_handler(conv_handler)
    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_error_handler(error_handler)
    
    logger.info("Invite Bot gestartet...")
    app.run_polling()

if __name__ == "__main__":
    main()
