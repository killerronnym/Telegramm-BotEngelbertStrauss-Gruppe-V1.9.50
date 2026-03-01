import logging
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from web_dashboard.app.models import Birthday, BotSettings
from web_dashboard.app import db
from shared_bot_utils import get_shared_flask_app
import json
import re
from datetime import datetime

logger = logging.getLogger(__name__)

# Pattern to match "DD MM", "DD.MM.", "DD.MM"
DATE_PATTERN = re.compile(r'^(\d{1,2})[\s\.]+(\d{1,2})\.?$')

def get_birthday_settings():
    flask_app = get_shared_flask_app()
    with flask_app.app_context():
        setting = BotSettings.query.filter_by(bot_name='birthday').first()
        if not setting:
            return {
                'registration_text': 'Dein Geburtstag ({day}.{month}.) wurde erfolgreich eingetragen!',
                'congratulation_text': 'Herzlichen Glückwunsch zum Geburtstag, {user}!',
                'announce_time': '00:01'
            }
        return json.loads(setting.config_json)

async def set_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    if not context.args:
        await update.message.reply_text("Bitte gib dein Datum an, z.B. /gb 15 08 oder /geburtstag 15.08.")
        return

    text_args = " ".join(context.args)
    match = DATE_PATTERN.match(text_args.strip())
    
    if not match:
        await update.message.reply_text("Ungültiges Format. Erwartet wird: DD MM oder DD.MM.")
        return
        
    day = int(match.group(1))
    month = int(match.group(2))
    
    if not (1 <= month <= 12) or not (1 <= day <= 31):
        await update.message.reply_text("Das ist kein gültiges Datum.")
        return
        
    flask_app = get_shared_flask_app()
    with flask_app.app_context():
        birthday = Birthday.query.filter_by(telegram_user_id=user.id).first()
        if birthday:
            birthday.day = day
            birthday.month = month
            birthday.chat_id = chat_id
            birthday.username = user.username
            birthday.first_name = user.first_name
        else:
            birthday = Birthday(
                telegram_user_id=user.id,
                chat_id=chat_id,
                username=user.username,
                first_name=user.first_name,
                day=day,
                month=month
            )
            db.session.add(birthday)
        db.session.commit()
        
        settings = get_birthday_settings()
        reply_text = settings.get('registration_text', 'Dein Geburtstag ({day}.{month}.) wurde erfolgreich eingetragen!')
        
        # Replace placeholders
        reply_text = reply_text.replace('{day}', str(day)).replace('{month}', str(month))
        await update.message.reply_text(reply_text)

async def check_birthdays(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now()
    
    settings = get_birthday_settings()
    # Check if the current time matches the configured time
    # e.g., '00:01'
    announce_time = settings.get('announce_time', '00:01')
    current_time_str = today.strftime('%H:%M')
    
    if current_time_str != announce_time:
        return
        
    flask_app = get_shared_flask_app()
    with flask_app.app_context():
        birthdays = Birthday.query.filter_by(day=today.day, month=today.month).all()
        for b in birthdays:
            if b.chat_id:
                try:
                    text = settings.get('congratulation_text', 'Herzlichen Glückwunsch zum Geburtstag, {user}!')
                    name = b.first_name if b.first_name else f"@{b.username}"
                    text = text.replace('{user}', name)
                    
                    await context.bot.send_message(chat_id=b.chat_id, text=text)
                    logger.info(f"Geburtstagsgruß gesendet an {name} in Chat {b.chat_id}")
                except Exception as e:
                    logger.error(f"Fehler beim Senden des Geburtstagsgrußes für {b.telegram_user_id}: {e}")

def get_handlers():
    return [
        CommandHandler("geburtstag", set_birthday),
        CommandHandler("gb", set_birthday)
    ]

def get_fallback_handlers():
    return []

def setup_jobs(job_queue):
    # Check every minute. The job itself verifies if current time matches 'announce_time'
    job_queue.run_repeating(check_birthdays, interval=60, first=10)
