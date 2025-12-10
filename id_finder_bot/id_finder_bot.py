
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
ADMINS_FILE = os.path.join(os.path.dirname(BASE_DIR), 'dashboard', 'admins.json') # NEW: Admins File in dashboard directory


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

def load_admins(): # NEW: Load Admins Function
    if not os.path.exists(ADMINS_FILE):
        return {}
    try:
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Fehler beim Laden der Admin-Daten: {e}")
        return {}

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

# NEW: Permission Check Decorator
def check_permission(permission_key: str):
    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = str(update.effective_user.id)
            admins = load_admins()
            
            # If user is not in admins.json, they have no permissions
            if user_id not in admins:
                await update.message.reply_text("Du hast keine Berechtigung für diesen Befehl.")
                log_command(user_id, update.effective_user.full_name, f"PERMISSION_DENIED: {func.__name__}")
                return
            
            # Check if the specific permission is set to True
            if not admins[user_id]['permissions'].get(permission_key, False):
                await update.message.reply_text("Du hast keine Berechtigung für diesen Befehl.")
                log_command(user_id, update.effective_user.full_name, f"PERMISSION_DENIED: {func.__name__}")
                return
            
            return await func(update, context, *args, **kwargs)
        return wrapper
    return decorator


# --- Befehls-Handler ---

# Basis-Moderation & IDs

@check_permission("can_see_ids") 
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    chat = update.effective_chat
    topic_id = update.message.message_thread_id
    
    response = f"👤 Deine ID: `{user.id}`\n"
    response += f"💬 Chat ID: `{chat.id}`\n"
    if topic_id:
        response += f"🧵 Topic ID: `{topic_id}`"
        
    if update.message.reply_to_message:
        original_msg = update.message.reply_to_message
        original_user = original_msg.from_user
        response += f"\n\n👇 **Ziel-Nachricht** 👇\n"
        response += f"👤 User ID: `{original_user.id}`\n"
        response += f"📄 Message ID: `{original_msg.message_id}`"

    await update.message.reply_text(response, parse_mode='Markdown')
    log_command(user.id, user.full_name, "/id")

@check_permission("can_see_ids") 
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    response = f"💬 Die ID dieses Chats ist: `{chat.id}`"
    if update.effective_message.message_thread_id:
        response += f"\n🧵 Topic ID: `{update.effective_message.message_thread_id}`"
    await update.message.reply_text(response, parse_mode='Markdown')
    log_command(update.effective_user.id, update.effective_user.full_name, "/chatid")

@check_permission("can_see_ids") 
async def get_topic_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message.message_thread_id:
        response = f"🧵 Topic ID: `{update.effective_message.message_thread_id}`"
    else:
        response = "Diese Nachricht befindet sich in keinem spezifischen Topic oder das Forum-Feature ist nicht aktiv."
    await update.message.reply_text(response, parse_mode='Markdown')
    log_command(update.effective_user.id, update.effective_user.full_name, "/topicid")


@check_permission("can_see_ids") 
async def get_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    response = f"👤 Deine User ID ist: `{user.id}`"
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        response += f"\n\n👇 **Ziel-Nachricht User ID** 👇\n👤 User ID: `{target_user.id}`"
    await update.message.reply_text(response, parse_mode='Markdown')
    log_command(user.id, user.full_name, "/userid")

@check_permission("can_warn") 
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

@check_permission("can_warn") 
async def get_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user, args = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text("Bitte antworte auf eine Nachricht oder gib eine User-ID an.")
        return
        
    data = load_moderation_data()
    user_id_str = str(target_user.id)
    
    if user_id_str in data and data[user_id_str]["warns"] > 0:
        msg_text = f"⚠️ Verwarnungen für {target_user.full_name}:\nAnzahl: {data[user_id_str]['warns']}\n\nHistorie:\n"
        for entry in data[user_id_str]["history"][-5:]: # Letzte 5 anzeigen
            msg_text += f"- {entry['date'][:10]}: {entry['reason']} (von {entry['by']})\n"
    else:
        msg_text = f"✅ Keine Verwarnungen für {target_user.full_name} gefunden."

    await update.message.reply_text(msg_text, parse_mode='Markdown')

@check_permission("can_warn") 
async def unwarn_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user, args = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text("Bitte antworte auf eine Nachricht oder gib eine User-ID an.")
        return

    data = load_moderation_data()
    user_id_str = str(target_user.id)
    
    if user_id_str in data and data[user_id_str]["warns"] > 0:
        data[user_id_str]["warns"] -= 1
        save_moderation_data(data)
        msg_text = f"✅ Eine Verwarnung für {target_user.full_name} wurde entfernt. Aktuell: {data[user_id_str]['warns']}"
    else:
        msg_text = f"ℹ️ {target_user.full_name} hat keine Verwarnungen."

    await update.message.reply_text(msg_text, parse_mode='Markdown')

@check_permission("can_warn") 
async def clear_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user, args = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text("Bitte antworte auf eine Nachricht oder gib eine User-ID an.")
        return

    data = load_moderation_data()
    user_id_str = str(target_user.id)
    
    if user_id_str in data:
        data[user_id_str]["warns"] = 0
        data[user_id_str]["history"] = [] # Optional: History auch löschen? Hier ja.
        save_moderation_data(data)
        msg_text = f"✅ Alle Verwarnungen für {target_user.full_name} wurden zurückgesetzt."
    else:
        msg_text = f"ℹ️ {target_user.full_name} hat keine Verwarnungen."

    await update.message.reply_text(msg_text, parse_mode='Markdown')


@check_permission("can_kick") 
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

@check_permission("can_ban") 
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

@check_permission("can_ban") 
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user, args = await get_target_user(update, context)
    if not target_user and args:
        # Versuch, ID aus Argumenten zu lesen, da User nicht im Chat sein muss
        try:
            user_id = int(args[0])
        except ValueError:
            await update.message.reply_text("Bitte gib eine gültige User-ID an.")
            return
    elif target_user:
        user_id = target_user.id
    else:
        await update.message.reply_text("Bitte gib eine User-ID an.")
        return

    try:
        await context.bot.unban_chat_member(update.effective_chat.id, user_id)
        await update.message.reply_text(f"✅ Benutzer mit ID `{user_id}` wurde entbannt.", parse_mode='Markdown')
        log_command(update.effective_user.id, update.effective_user.full_name, "/unban", user_id)

    except TelegramError as e:
        await update.message.reply_text(f"Fehler beim Entbannen: {e}")


@check_permission("can_mute") 
async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user, args = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text("Bitte antworte auf eine Nachricht oder gib eine User-ID an, um jemanden stummzuschalten.")
        return

    duration_str = None
    reason = "Kein Grund angegeben"

    if args:
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
            duration_str = args.pop(0)
            reason = " ".join(args) if args else "Kein Grund angegeben"
        else:
            reason = " ".join(args)

    if not duration_str:
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

@check_permission("can_mute") 
async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user, args = await get_target_user(update, context)
    if not target_user:
        await update.message.reply_text("Bitte antworte auf eine Nachricht oder gib eine User-ID an.")
        return

    try:
        # Standard-Berechtigungen wiederherstellen (oder anpassen je nach Gruppen-Einstellungen)
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target_user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_media_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True
            )
        )
        await update.message.reply_text(f"🔊 {target_user.full_name} wurde entstummt.")
        log_command(update.effective_user.id, update.effective_user.full_name, "/unmute", target_user.id)
    except TelegramError as e:
        await update.message.reply_text(f"Fehler beim Aufheben der Stummschaltung: {e}")


# Nachrichten-Management

@check_permission("can_manage_messages")
async def delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Bitte antworte auf die Nachricht, die gelöscht werden soll.")
        return
    
    try:
        await update.message.reply_to_message.delete()
        await update.message.delete() # Befehl selbst auch löschen
    except TelegramError as e:
        await update.message.reply_text(f"Fehler beim Löschen: {e}")

@check_permission("can_manage_messages")
async def purge_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Bitte antworte auf die erste Nachricht, ab der gelöscht werden soll.")
        return

    message_id = update.message.reply_to_message.message_id
    current_id = update.message.message_id
    chat_id = update.effective_chat.id
    
    # Simple Loop Delete (Bulk Delete hat Limits und Zeitbeschränkungen)
    deleted_count = 0
    # Versuch die IDs dazwischen zu raten/löschen (nicht perfekt, aber gängig)
    ids_to_delete = list(range(message_id, current_id + 1))
    
    for mid in ids_to_delete:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
            deleted_count += 1
        except Exception:
            pass # Nachricht existiert nicht mehr oder zu alt
            
    confirmation = await update.message.reply_text(f"🗑️ {deleted_count} Nachrichten gelöscht.")
    # Kurze Pause und dann Bestätigung löschen
    # (Dies erfordert JobQueue oder sleep, hier vereinfacht lassen wir es stehen oder löschen manuell)

@check_permission("can_manage_messages")
async def pin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        await update.message.reply_text("Bitte antworte auf die Nachricht, die angepinnt werden soll.")
        return
    try:
        await update.message.reply_to_message.pin()
        await update.message.reply_text("📌 Nachricht angepinnt.")
    except TelegramError as e:
        await update.message.reply_text(f"Fehler beim Anpinnen: {e}")

@check_permission("can_manage_messages")
async def unpin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message:
        # Wenn kein Reply, versuche letzten Pin zu entfernen oder alle? 
        # Telegram API unpin_chat_message unpinnt die letzte oder spezifische.
        try:
            await context.bot.unpin_chat_message(chat_id=update.effective_chat.id)
            await update.message.reply_text("📌 Pin entfernt.")
        except TelegramError as e:
            await update.message.reply_text(f"Fehler beim Entfernen des Pins: {e}")
        return

    try:
        await update.message.reply_to_message.unpin()
        await update.message.reply_text("📌 Pin entfernt.")
    except TelegramError as e:
        await update.message.reply_text(f"Fehler beim Entfernen des Pins: {e}")

@check_permission("can_manage_messages")
async def lock_feature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Bitte gib an, was gesperrt werden soll: media, links, etc. (Noch nicht voll impl.)")
        return
    feature = context.args[0].lower()
    await update.message.reply_text(f"🔒 {feature} wurde gesperrt (Placeholder - Logik muss ergänzt werden).")

@check_permission("can_manage_messages")
async def unlock_feature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Bitte gib an, was entsperrt werden soll.")
        return
    feature = context.args[0].lower()
    await update.message.reply_text(f"🔓 {feature} wurde entsperrt (Placeholder).")


# Admin Panel & Rollen

@check_permission("can_see_logs")
async def get_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = load_admins()
    if not admins:
        await update.message.reply_text("Keine Admins konfiguriert.")
        return

    response = "**Aktuelle Admins:**\n"
    for admin_id, admin_data in admins.items():
        perms_list = [p for p, granted in admin_data.get('permissions', {}).items() if granted]
        perms_str = ', '.join(perms_list) if perms_list else "Keine Rechte"
        response += f"- {admin_data.get('name', 'Unbekannt')} (`{admin_id}`): {perms_str}\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')
    log_command(update.effective_user.id, update.effective_user.full_name, "/adminlist")

# Dummy Handler für noch nicht implementierte Funktionen, um Fehler zu vermeiden
async def not_implemented(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Dieser Befehl ist noch nicht vollständig implementiert.")


# --- Bot Start ---
if __name__ == "__main__":
    config = load_config()
    token = config.get("bot_token")
    
    if not token:
        logger.info("ID Finder Bot ist deaktiviert oder Token fehlt.")
    else:
        app = ApplicationBuilder().token(token).build()
        
        # Basis-Moderation
        app.add_handler(CommandHandler("id", get_id))
        app.add_handler(CommandHandler("chatid", get_chat_id))
        app.add_handler(CommandHandler("userid", get_user_id))
        app.add_handler(CommandHandler("topicid", get_topic_id))
        
        app.add_handler(CommandHandler("warn", warn_user))
        app.add_handler(CommandHandler("warnings", get_warnings))
        app.add_handler(CommandHandler("unwarn", unwarn_user))
        app.add_handler(CommandHandler("clearwarnings", clear_warnings))
        
        app.add_handler(CommandHandler("kick", kick_user))
        app.add_handler(CommandHandler("ban", ban_user))
        app.add_handler(CommandHandler("unban", unban_user))
        app.add_handler(CommandHandler("mute", mute_user))
        app.add_handler(CommandHandler("unmute", unmute_user))

        # Nachrichten
        app.add_handler(CommandHandler("del", delete_message))
        app.add_handler(CommandHandler("purge", purge_messages))
        app.add_handler(CommandHandler("pin", pin_message))
        app.add_handler(CommandHandler("unpin", unpin_message))
        app.add_handler(CommandHandler("lock", lock_feature))
        app.add_handler(CommandHandler("unlock", unlock_feature))

        # Auto-Mod & Spam (Platzhalter)
        app.add_handler(CommandHandler("antispam", not_implemented))
        app.add_handler(CommandHandler("setflood", not_implemented))
        app.add_handler(CommandHandler("setlinkmode", not_implemented))
        app.add_handler(CommandHandler("blacklist", not_implemented))

        # Admin Panel Commands
        app.add_handler(CommandHandler("adminlist", get_admin_list))
        app.add_handler(CommandHandler("mod", not_implemented))
        app.add_handler(CommandHandler("permissions", not_implemented))
        app.add_handler(CommandHandler("setrole", not_implemented))
        
        logger.info("🆔 ID Finder Bot läuft...")
        app.run_polling()
