import logging
import os
import sys
from datetime import datetime
from typing import Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

from flask import Flask
from web_dashboard.app.models import db, BotSettings, InviteApplication, InviteLog

# Import shared utils for DB URL resolution
from shared_bot_utils import get_db_url, get_bot_config, is_bot_active

# --- Database Helper ---
def get_db_session():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = get_db_url()
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app

flask_app = get_db_session()

# --- Logging Setup --- 
# Corrected paths for logging to be robust regardless of where the script is run from.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WEB_DASHBOARD_DIR = os.path.join(PROJECT_ROOT, 'web_dashboard')
INVITE_BOT_LOG_FILE = os.path.join(WEB_DASHBOARD_DIR, "invite_bot.log")

# Ensure directories exist before logging attempts
os.makedirs(WEB_DASHBOARD_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(INVITE_BOT_LOG_FILE, encoding='utf-8'), # Bot's own log
        logging.StreamHandler(sys.stdout) # Output to console as well
    ]
)
logger = logging.getLogger(__name__)

# Globale Variablen komplett ausgebaut, Nutzung von SQLite DB!

def log_user_interaction(user_id, username, message_text):
    try:
        with flask_app.app_context():
            log_entry = InviteLog(telegram_user_id=user_id, username=username or "Unknown", action=message_text)
            db.session.add(log_entry)
            db.session.commit()
    except Exception as e:
        logger.error(f"Fehler beim Schreiben in die Datenbank (InviteLog): {e}")

# Conversation States
ASKING_QUESTIONS, CONFIRMING_RULES = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_bot_active('invite'): return
    config = get_bot_config('invite')
    if not config.get('is_enabled'):
        await update.message.reply_text("Der Bot ist zur Zeit deaktiviert.")
        return
    await update.message.reply_text(config.get('start_message', 'Willkommen! Schreibe /letsgo um zu starten.'))
    log_user_interaction(update.effective_user.id, update.effective_user.username, "/start command aufgerufen")

async def letsgo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_bot_active('invite'): return ConversationHandler.END
    config = get_bot_config('invite')
    if not config.get('is_enabled'):
        await update.message.reply_text("Der Bot ist zur Zeit deaktiviert.")
        return ConversationHandler.END

    with flask_app.app_context():
        existing_app = InviteApplication.query.filter_by(telegram_user_id=update.effective_user.id, status='pending').first()
        if existing_app:
            await update.message.reply_text("Du hast bereits eine laufende oder ausstehende Bewerbung, die von den Administratoren geprüft wird.")
            return ConversationHandler.END

    fields = [f for f in config.get('form_fields', []) if f.get('enabled', True)]
    if not fields:
        await update.message.reply_text("Keine Fragen konfiguriert. Admin kontaktieren.")
        return ConversationHandler.END
    context.user_data.update({'fields': fields, 'current_field_index': 0, 'answers': {}})
    await update.message.reply_text(fields[0].get('label', 'Frage?'))
    return ASKING_QUESTIONS

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    idx = context.user_data.get('current_field_index', 0)
    fields = context.user_data.get('fields', [])
    field = fields[idx]
    answer = None

    if field['type'] == 'photo':
        if not update.message.photo:
            await update.message.reply_text("Bitte sende ein Foto.")
            return ASKING_QUESTIONS
        answer = update.message.photo[-1].file_id
    else:
        answer_text = update.message.text
        if not answer_text and field.get('required'):
            await update.message.reply_text("Diese Antwort ist erforderlich.")
            return ASKING_QUESTIONS
        if field['type'] == 'number':
            if not answer_text.isdigit():
                await update.message.reply_text("Bitte sende eine gültige Zahl.")
                return ASKING_QUESTIONS
            answer = int(answer_text)
        else:
            answer = answer_text
    
    log_user_interaction(user.id, user.username, f"Antwort auf {field['id']}: {answer if isinstance(answer, (str, int)) else 'Photo'}")
    context.user_data['answers'][field['id']] = answer
    idx += 1
    context.user_data['current_field_index'] = idx
    
    if idx < len(fields):
        await update.message.reply_text(fields[idx].get('label', 'Nächste Frage?'))
        return ASKING_QUESTIONS
    else:
        config = get_bot_config('invite')
        await update.message.reply_text(f"{config.get('rules_message', 'Danke!')}\n\nSchreibe 'ok' zum Bestätigen.")
        return CONFIRMING_RULES

async def post_profile(bot, profile_data: Dict[str, Any], is_approval_post: bool = False):
    target_chat_id = profile_data['target_chat_id']
    kwargs = {"chat_id": target_chat_id}
    
    topic_id_key = 'whitelist_approval_topic_id' if is_approval_post else 'topic_id'
    topic_id = profile_data.get(topic_id_key)

    if topic_id and str(topic_id).isdigit():
        kwargs["message_thread_id"] = int(topic_id)

    if profile_data.get('photo_id'):
        kwargs.update({"photo": profile_data['photo_id'], "caption": profile_data['text']})
        await bot.send_photo(**kwargs)
    else:
        kwargs["text"] = profile_data['text']
        await bot.send_message(**kwargs)

async def handle_rules_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not update.message.text or update.message.text.lower().strip() != 'ok':
        await update.message.reply_text('Bitte schreibe "ok" zum Bestätigen.')
        return CONFIRMING_RULES

    config = get_bot_config('invite')
    chat_id_str = config.get('main_chat_id')
    if not chat_id_str:
        await update.message.reply_text("Bot nicht konfiguriert.")
        return ConversationHandler.END
    target_chat_id = int(chat_id_str) if chat_id_str.lstrip('-').isdigit() else chat_id_str
    
    try:
        member = await context.bot.get_chat_member(chat_id=target_chat_id, user_id=user.id)
        if member and member.status == "kicked":
            await update.message.reply_text(config.get('blocked_message', 'Du bist gesperrt.'))
            return ConversationHandler.END
    except BadRequest:
        pass

    answers = context.user_data['answers']
    ordered_fields = context.user_data.get('fields', [])
    steckbrief_lines = [f"🎉 Steckbrief von {user.full_name} (@{user.username or 'N/A'})"]
    photo_file_id = None
    for field in ordered_fields:
        answer = answers.get(field['id'])
        if answer is None or (isinstance(answer, str) and answer.lower().strip() == 'nein'):
            continue
        if field['type'] == 'photo':
            photo_file_id = answer
        else:
            steckbrief_lines.append(f"{field.get('emoji', '🔹')} {field.get('display_name', field['id'])}: {answer}")
    
    profile_data = {
        'text': "\n".join(steckbrief_lines), 'photo_id': photo_file_id,
        'target_chat_id': target_chat_id, 'topic_id': config.get('topic_id'),
        'whitelist_approval_topic_id': config.get('whitelist_approval_topic_id')
    }

    if config.get('whitelist_enabled'):
        approval_chat_id_str = config.get('whitelist_approval_chat_id')
        if not approval_chat_id_str:
            await update.message.reply_text("Whitelist ist aktiv, aber kein Admin-Chat konfiguriert.")
            return ConversationHandler.END
        
        approval_chat_id = int(approval_chat_id_str) if approval_chat_id_str.lstrip('-').isdigit() else approval_chat_id_str
        
        # In Datenbank sichern anstatt in Dictionaries
        with flask_app.app_context():
            existing = InviteApplication.query.filter_by(telegram_user_id=user.id).first()
            if existing:
                existing.status = 'pending'
                existing.answers = profile_data
                existing.full_name = user.full_name
                existing.username = user.username
            else:
                new_app = InviteApplication(
                    telegram_user_id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                    answers_json=json.dumps(profile_data),
                    status='pending'
                )
                db.session.add(new_app)
            db.session.commit()
        
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Annehmen", callback_data=f"whitelist_accept_{user.id}"),
                                          InlineKeyboardButton("❌ Ablehnen", callback_data=f"whitelist_reject_{user.id}")]])
        
        approval_post_data = profile_data.copy()
        approval_post_data['target_chat_id'] = approval_chat_id
        await post_profile(context.bot, approval_post_data, is_approval_post=True)
        await context.bot.send_message(approval_chat_id, "Neue Anfrage zur Freischaltung:", reply_markup=keyboard, 
                                       message_thread_id=approval_post_data.get('whitelist_approval_topic_id') if str(approval_post_data.get('whitelist_approval_topic_id')).isdigit() else None)
        await update.message.reply_text(config.get('whitelist_pending_message', 'Dein Antrag wird geprüft.'))
    else:
        try:
            member = await context.bot.get_chat_member(chat_id=target_chat_id, user_id=user.id)
            if member and member.status in ["creator", "administrator", "member"]:
                profile_data['text'] = profile_data['text'].replace("Steckbrief von", "Willkommen in der Gruppe!")
                await post_profile(context.bot, profile_data)
                await update.message.reply_text("Dein Steckbrief wurde gepostet!")
            else:
                raise BadRequest("User not a member")
        except BadRequest:
            # Ohne Whitelist direkt Link ausgeben und lokal als 'accepted' markieren
            with flask_app.app_context():
                new_app = InviteApplication(
                    telegram_user_id=user.id,
                    username=user.username,
                    full_name=user.full_name,
                    answers_json=json.dumps(profile_data),
                    status='accepted'
                )
                db.session.add(new_app)
                db.session.commit()
                
            link = await context.bot.create_chat_invite_link(chat_id=target_chat_id, member_limit=1)
            await update.message.reply_text(f"Danke! Hier ist dein Link:\n{link.invite_link}")

    return ConversationHandler.END

async def handle_whitelist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    action, user_id_str = query.data.split('_', 2)[1:]
    user_id = int(user_id_str)
    admin_user = query.from_user
    config = get_bot_config('invite')

    with flask_app.app_context():
        application = InviteApplication.query.filter_by(telegram_user_id=user_id).first()
        
        if not application or application.status != 'pending':
            await query.edit_message_text(f"Diese Anfrage ist nicht mehr verfügbar (vielleicht schon bearbeitet?).")
            return
            
        profile_data = application.answers

        if action == "accept":
            target_chat_id = profile_data.get('target_chat_id')
            if target_chat_id:
                link = await context.bot.create_chat_invite_link(chat_id=target_chat_id, member_limit=1)
                await context.bot.send_message(user_id, f"Gute Nachrichten! Deine Anfrage wurde angenommen. Hier ist dein Einladungslink:\n{link.invite_link}")
                await query.edit_message_text(f"✅ Angenommen von {admin_user.full_name}. Der Nutzer hat den Link erhalten.")
                application.status = 'accepted'
                db.session.commit()
            else:
                await query.edit_message_text("Fehler: Target Chat ID nicht gefunden.")
                application.status = 'rejected'
                db.session.commit()
                
        elif action == "reject":
            rejection_message = config.get('whitelist_rejection_message', 'Deine Anfrage wurde leider abgelehnt.')
            await context.bot.send_message(user_id, rejection_message)
            await query.edit_message_text(f"❌ Abgelehnt von {admin_user.full_name}. Der Nutzer wurde benachrichtigt.")
            application.status = 'rejected'
            db.session.commit()

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.chat_member or not update.chat_member.new_chat_member or update.chat_member.new_chat_member.status != "member":
        return

    user_id = update.chat_member.new_chat_member.user.id
    
    with flask_app.app_context():
        application = InviteApplication.query.filter_by(telegram_user_id=user_id, status='accepted').first()
        if application:
            profile_data = application.answers
            if profile_data and 'text' in profile_data:
                profile_data['text'] = profile_data['text'].replace("Steckbrief von", "Willkommen in der Gruppe!")
                await post_profile(context.bot, profile_data)
                
            application.status = 'completed'
            db.session.commit()

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Prozess abgebrochen.")
    return ConversationHandler.END

def get_handlers():
    """Gleicht handlers für den Master Bot zurück."""
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("letsgo", letsgo)],
        states={
            ASKING_QUESTIONS: [MessageHandler(filters.TEXT | filters.PHOTO, handle_answer)],
            CONFIRMING_RULES: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_rules_confirmation)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    return [
        conv_handler,
        CommandHandler("start", start),
        CallbackQueryHandler(handle_whitelist_callback, pattern=r'^whitelist_'),
        ChatMemberHandler(handle_new_member, ChatMemberHandler.CHAT_MEMBER)
    ]

# Nur wenn direkt ausgeführt (Legacy Fallback)
if __name__ == "__main__":
    logger.error("Dieses Skript sollte nicht direkt ausgeführt werden. Bitte main_bot.py nutzen.")
