import logging
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, ConversationHandler, filters, ContextTypes
from shared_bot_utils import get_shared_flask_app
try:
    from web_dashboard.app.models import Birthday, db, AutoCleanupTask, BotSettings, IDFinderUser
except ImportError:
    # Fallback für Unittests oder wenn Pfade abweichen
    Birthday = None
    AutoCleanupTask = None
    BotSettings = None
    IDFinderUser = None
    db = None
import json
import re
import os
import subprocess
import random
from datetime import datetime, timedelta
import pytz
from PIL import Image, ImageDraw, ImageFont, ImageFilter

logger = logging.getLogger("BirthdayBot")
logger.setLevel(logging.INFO)

WAITING_FOR_DATE = 1

# Erlaubt Formate wie: "15 08", "15.08.", "15.08", "15.08.1990", "15 08 1990"
DATE_PATTERN = re.compile(r'^(\d{1,2})[\s\.]+(\d{1,2})(?:[\s\.]+(\d{4}))?\.?$')

def get_birthday_settings():
    flask_app = get_shared_flask_app()
    with flask_app.app_context():
        setting = BotSettings.query.filter_by(bot_name='birthday').first()
        if not setting:
            return {
                'registration_text': 'Dein Geburtstag ({day}.{month}.) wurde erfolgreich eingetragen!',
                'congratulation_text': 'Herzlichen Glückwunsch zum Geburtstag, {user}!',
                'prompt_text': '🎂 <b>Geburtstags-Bot</b>\n\nWann hast du Geburtstag?\nBitte schreibe es im Format <code>Tag.Monat</code> oder <code>Tag.Monat.Jahr</code>.\n<i>(Beispiel: 15.08. oder 15.08.1990 - das Jahr ist komplett freiwillig!)</i>\n\nWenn du abbrechen möchtest, tippe /cancel.',
                'error_format_text': 'Das war leider das falsche Format.\nBeispiele: `15.08.` oder `15 08 1990`\nVersuche es nochmal oder tippe /cancel.',
                'error_date_text': 'Das ist leider kein echtes Kalenderdatum. Bitte versuche es noch einmal:',
                'cancel_text': 'Geburtstags-Eintragung abgebrochen.',
                'announce_time': '00:01',
                'target_chat_id': '',
                'target_topic_id': '',
                'auto_delete_registration': False 
            }
        return json.loads(setting.config_json)

# --- Helper for Auto-Cleanup ---
def schedule_msg_cleanup(chat_id, message_id, delay_seconds=60):
    """Schedules a message for automatic deletion via the shared DB table."""
    try:
        settings = get_birthday_settings()
        if not settings.get('auto_delete_registration'):
            return
            
        flask_app = get_shared_flask_app()
        with flask_app.app_context():
            cleanup_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
            task = AutoCleanupTask(
                chat_id=chat_id,
                message_id=message_id,
                cleanup_at=cleanup_at,
                status='pending'
            )
            db.session.add(task)
            db.session.commit()
    except Exception as e:
        logger.error(f"Error scheduling birthday cleanup: {e}")

async def start_birthday_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from shared_bot_utils import is_bot_active
    if not is_bot_active('birthday'):
        logger.info("Birthday registration ignored: bot is inactive in settings.")
        return ConversationHandler.END

    logger.info(f"Starting birthday registration for user {update.effective_user.id}")
    settings = get_birthday_settings()
    text = settings.get('prompt_text', '🎂 <b>Geburtstags-Bot</b>...')
    
    if update.message:
        kwargs = {'text': text, 'parse_mode': 'HTML'}
        if update.message.is_topic_message:
            kwargs['message_thread_id'] = update.message.message_thread_id
            
        sent_msg = await update.message.reply_text(**kwargs)
        # Auto-Cleanup
        schedule_msg_cleanup(update.effective_chat.id, update.message.message_id)
        schedule_msg_cleanup(update.effective_chat.id, sent_msg.message_id)

    return WAITING_FOR_DATE

async def handle_date_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    text_input = update.message.text.strip()
    
    match = DATE_PATTERN.match(text_input)
    settings = get_birthday_settings()
    
    if not match:
        msg = settings.get('error_format_text', "Falsches Format.")
        kwargs = {'text': msg, 'parse_mode': 'Markdown'}
        if update.message.is_topic_message:
            kwargs['message_thread_id'] = update.message.message_thread_id
        sent_msg = await update.message.reply_text(**kwargs)
        schedule_msg_cleanup(chat_id, update.message.message_id)
        schedule_msg_cleanup(chat_id, sent_msg.message_id)
        return WAITING_FOR_DATE
        
    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3)) if match.group(3) else None
    
    if not (1 <= month <= 12) or not (1 <= day <= 31):
        msg = settings.get('error_date_text', "Ungültiges Datum.")
        kwargs = {'text': msg}
        if update.message.is_topic_message:
            kwargs['message_thread_id'] = update.message.message_thread_id
        sent_msg = await update.message.reply_text(**kwargs)
        schedule_msg_cleanup(chat_id, update.message.message_id)
        schedule_msg_cleanup(chat_id, sent_msg.message_id)
        return WAITING_FOR_DATE

    flask_app = get_shared_flask_app()
    with flask_app.app_context():
        # User in DB sicherstellen
        id_user = IDFinderUser.query.filter_by(telegram_id=user.id).first()
        if not id_user:
            id_user = IDFinderUser(telegram_id=user.id, first_name=user.first_name, username=user.username)
            db.session.add(id_user)

        birthday = Birthday.query.filter_by(telegram_user_id=user.id).first()
        if birthday:
            birthday.day, birthday.month, birthday.year = day, month, year
            birthday.chat_id, birthday.username, birthday.first_name = chat_id, user.username, user.first_name
            birthday.topic_id = update.message.message_thread_id if update.message.is_topic_message else None
        else:
            birthday = Birthday(
                telegram_user_id=user.id, chat_id=chat_id,
                topic_id=update.message.message_thread_id if update.message.is_topic_message else None,
                username=user.username, first_name=user.first_name,
                day=day, month=month, year=year
            )
            db.session.add(birthday)
        db.session.commit()
        
        reply_text = settings.get('registration_text', 'Erfolgreich!').replace('{day}', f"{day:02d}").replace('{month}', f"{month:02d}")
        if year: reply_text += f"\n(Jahrgang: {year} gespeichert)"
            
        sent_msg = await update.message.reply_text(reply_text, 
            message_thread_id=update.message.message_thread_id if update.message.is_topic_message else None)
        
        schedule_msg_cleanup(chat_id, update.message.message_id) 
        schedule_msg_cleanup(chat_id, sent_msg.message_id)
        
    return ConversationHandler.END

async def get_best_user_photo(bot, user_id):
    """
    Versucht das bestmögliche Bild für den User zu finden.
    Priorität:
    1. Foto aus dem Steckbrief (InviteApplication)
    2. Cached Photo aus IDFinderUser
    3. Normales Telegram-Profilbild (Avatar-Cache)
    """
    try:
        from web_dashboard.app.models import InviteApplication, IDFinderUser, db
        flask_app = get_shared_flask_app()
        
        file_id = None
        
        with flask_app.app_context():
            # 1. Check InviteApplication (Steckbrief)
            app = InviteApplication.query.filter_by(telegram_user_id=user_id).first()
            if app:
                answers = app.answers
                # Priorisiere den Namen "photo"
                if answers.get('photo') and isinstance(answers['photo'], str):
                    if answers['photo'].startswith('AgAC'):
                        file_id = answers['photo']
                
                # Fallback: Suche nach dem ersten AgAC im JSON
                if not file_id:
                    for val in answers.values():
                        if isinstance(val, str) and val.startswith('AgAC'):
                            file_id = val
                            break
            
            # 2. Check IDFinderUser (Cached Photo ID)
            if not file_id:
                u = IDFinderUser.query.filter_by(telegram_id=user_id).first()
                if u and u.photo_file_id:
                    file_id = u.photo_file_id

        # Fallback auf lokalen Avatar-Cache (Profilbild)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        avatar_path = os.path.join(project_root, 'web_dashboard', 'app', 'static', 'avatars', f"{user_id}.jpg")
        
        if not file_id:
            if os.path.exists(avatar_path):
                return Image.open(avatar_path).convert('RGB')
            return None

        # Wenn wir eine File-ID haben, laden wir sie frisch von Telegram
        logger.info(f"Downloading best photo for user {user_id} using file_id {file_id[:10]}...")
        t_file = await bot.get_file(file_id)
        import io
        img_bytes = await t_file.download_as_bytearray()
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        
        # In Cache speichern
        os.makedirs(os.path.dirname(avatar_path), exist_ok=True)
        img.save(avatar_path, "JPEG", quality=90)
        
        return img
    except Exception as e:
        logger.error(f"Error getting best user photo for {user_id}: {e}")
        # Letzter Rettungsversuch: Lokaler Cache
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            avatar_path = os.path.join(project_root, 'web_dashboard', 'app', 'static', 'avatars', f"{user_id}.jpg")
            if os.path.exists(avatar_path):
                return Image.open(avatar_path).convert('RGB')
        except: pass
        return None

async def generate_birthday_gif(user_id, bot, output_path):
    """
    Generiert ein animiertes GIF mit dem Steckbrief-Bild als Hintergrund,
    aufsteigenden Ballons und fliegendem Konfetti.
    """
    try:
        # Bestmögliches Bild holen
        img_src = await get_best_user_photo(bot, user_id)
        
        if not img_src:
            bg = Image.new('RGB', (640, 640), color=(30, 45, 60))
        else:
            w, h = img_src.size
            size = min(w, h)
            left = (w - size) / 2
            top = (h - size) / 2
            bg = img_src.crop((left, top, left + size, top + size)).resize((640, 640), Image.LANCZOS)
        
        dimmer = Image.new('RGBA', (640, 640), (0, 0, 0, 40)) # Weniger Dimming da kein Text auf Bild
        bg.paste(dimmer, (0, 0), dimmer)

        # Animation Settings (Mehr Frames für flüssige Bewegung)
        num_frames = 35
        
        balloons = []
        for _ in range(8):
            balloons.append({
                'x': random.randint(50, 590),
                'y': random.randint(640, 940),
                'speed': random.uniform(8, 15),
                'color': random.choice([(255, 60, 60, 210), (60, 255, 60, 210), (60, 60, 255, 210), (255, 255, 60, 210), (255, 105, 180, 210)]),
                'size': random.randint(35, 55)
            })
        
        confetti = []
        for _ in range(60):
            confetti.append({
                'x': random.randint(0, 640),
                'y': random.randint(-640, 0),
                'speed': random.uniform(10, 25),
                'color': random.choice([(255,0,0), (0,255,0), (0,0,255), (255,255,0), (255,0,255), (255,255,255)]),
                'size': random.randint(3, 8)
            })

        frames = []
        for i in range(num_frames):
            frame = bg.copy().convert('RGBA')
            draw = ImageDraw.Draw(frame)
            
            # Konfetti (Regnet von oben nach ganz unten)
            for p in confetti:
                p['y'] += p['speed']
                if p['y'] > 660: p['y'] = -40
                draw.rectangle([p['x'], p['y'], p['x']+p['size'], p['y']+p['size']], fill=p['color'] + (180,))
            
            # Ballons (Steigen von unten nach ganz oben auf)
            for b in balloons:
                b['y'] -= b['speed']
                if b['y'] < -120: b['y'] = 700
                # Schnur
                draw.line([b['x'], b['y']+b['size'], b['x'], b['y']+b['size']+45], fill=(220,220,220,130), width=1)
                # Ballon Körper
                # Zeichne Ballon mit Glanz
                draw.ellipse([b['x']-b['size']/2, b['y'], b['x']+b['size']/2, b['y']+b['size']*1.2], fill=b['color'])
                # Highlight auf dem Ballon
                draw.ellipse([b['x']-b['size']/4, b['y']+5, b['x']-b['size']/8, b['y']+20], fill=(255,255,255,100))

            # KEIN TEXT MEHR AUF DEM BILD

            # Umwandeln für GIF (P-Modus mit optimierter Palette)
            # Wir nehmen adaptiv um Qualität zu erhalten
            frames.append(frame.convert('P', palette=Image.ADAPTIVE, colors=128))

        # Als GIF speichern (Loop aktiviert)
        # Duration 50ms = 20 FPS
        frames[0].save(output_path, format='GIF', append_images=frames[1:], save_all=True, duration=50, loop=0, optimize=True)
        return True
    except Exception as e:
        logger.error(f"Error generating birthday GIF: {e}")
        return False

async def send_birthday_wish(bot, user_id, chat_id, topic_id=None):
    """
    Sendet eine individuelle Geburtstagsgratulation mit GIF an einen Chat.
    """
    try:
        from web_dashboard.app.models import Birthday
        flask_app = get_shared_flask_app()
        settings = get_birthday_settings()
        
        with flask_app.app_context():
            b = Birthday.query.filter_by(telegram_user_id=user_id).first()
            if not b: return False
            
            display_name = b.first_name if b.first_name else (f"@{b.username}" if b.username else "Geburtstagskind")
            message_text = settings.get('congratulation_text', 'Herzlichen Glückwunsch!').replace('{user}', display_name)
            if '{age}' in message_text:
                now = datetime.now()
                message_text = message_text.replace('{age}', str(now.year - b.year) if b.year else '?')

            # GIF generieren
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'web_dashboard', 'app', 'static', 'media')
            os.makedirs(output_dir, exist_ok=True)
            gif_path = os.path.join(output_dir, f"birthday_{user_id}.gif")
            
            # Wir übergeben jetzt den Bot an den GIF-Generator
            success = await generate_birthday_gif(user_id, bot, gif_path)
            
            kwargs = {'chat_id': chat_id, 'caption': message_text, 'parse_mode': 'HTML'}
            if topic_id: kwargs['message_thread_id'] = int(topic_id)
            
            if success and os.path.exists(gif_path):
                with open(gif_path, 'rb') as animation:
                    await bot.send_animation(animation=animation, **kwargs)
                os.remove(gif_path)
            else:
                await bot.send_message(chat_id=chat_id, text=message_text, parse_mode='HTML', message_thread_id=topic_id)
            return True
    except Exception as e:
        logger.error(f"Error in send_birthday_wish: {e}")
        return False

async def cancel_registration(update: Update, context: ContextTypes.DEFAULT_TYPE):
    settings = get_birthday_settings()
    msg = settings.get('cancel_text', "Abgebrochen.")
    kwargs = {'text': msg}
    if update.message and update.message.is_topic_message:
        kwargs['message_thread_id'] = update.message.message_thread_id
    if update.message:
        sent_msg = await update.message.reply_text(**kwargs)
        schedule_msg_cleanup(update.effective_chat.id, update.message.message_id)
        schedule_msg_cleanup(update.effective_chat.id, sent_msg.message_id)
    return ConversationHandler.END

async def check_birthdays(context: ContextTypes.DEFAULT_TYPE, force: bool = False):
    tz = pytz.timezone('Europe/Berlin')
    now = datetime.now(tz)
    settings = get_birthday_settings()
    announce_time = settings.get('announce_time', '00:01')
    current_time_str = now.strftime('%H:%M')
    
    if not force and current_time_str != announce_time:
        return
            
    logger.info(f"Birthday Check: Triggere Gratulationen für {now.day}.{now.month}.")
    global_target_chat = settings.get('target_chat_id', '').strip()
    global_target_topic = settings.get('target_topic_id', '').strip()
        
    flask_app = get_shared_flask_app()
    with flask_app.app_context():
        birthdays = Birthday.query.filter_by(day=now.day, month=now.month).all()
        for b in birthdays:
            final_chat_id = str(global_target_chat) if global_target_chat else str(b.chat_id)
            if final_chat_id and not final_chat_id.startswith('-'):
                if final_chat_id.startswith('100') and len(final_chat_id) >= 10:
                    final_chat_id = f"-{final_chat_id}"
                elif len(final_chat_id) >= 10:
                    final_chat_id = f"-100{final_chat_id}"
            
            if final_chat_id:
                try:
                    target_topic = global_target_topic if global_target_topic else b.topic_id
                    await send_birthday_wish(context.bot, b.telegram_user_id, final_chat_id, target_topic)
                except Exception as e:
                    logger.error(f"Birthday Send Error: {e}")

def get_handlers():
    logger.info("Registering birthday bot handlers...")
    
    async def manual_birthday_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Starte manuellen Check...")
        await check_birthdays(context, force=True)

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("geburtstag", start_birthday_registration),
            CommandHandler("gb", start_birthday_registration),
            CommandHandler("testgb", manual_birthday_trigger)
        ],
        states={
            WAITING_FOR_DATE: [MessageHandler(filters.TEXT & (~filters.COMMAND), handle_date_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel_registration)],
        name="birthday_conv",
        persistent=True,
        allow_reentry=True
    )
    return [(conv_handler, 0)]

def get_fallback_handlers():
    return []

def setup_jobs(job_queue):
    job_queue.run_repeating(check_birthdays, interval=60, first=10)
