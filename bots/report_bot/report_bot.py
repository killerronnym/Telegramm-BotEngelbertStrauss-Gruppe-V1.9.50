import logging
import os
import json
import sys
import asyncio
from datetime import datetime, timedelta

# Setup Project Root for imports
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BOT_DIR))
sys.path.append(PROJECT_ROOT)

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode, ChatMemberStatus
import html

from web_dashboard.app.models import db, BotSettings, ReportedMessage, IDFinderUser, IDFinderWarning, IDFinderMessage
from shared_bot_utils import is_bot_active, get_bot_config, get_shared_flask_app

flask_app = get_shared_flask_app()
logger = logging.getLogger(__name__)

# In-memory cooldown storage: {user_id: last_report_time}
report_cooldowns = {}
COOLDOWN_SECONDS = 60

def get_report_config():
    return get_bot_config("report_bot") or {
        "is_active": False,
        "target_chat_id": None,
        "target_topic_id": None
    }

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Check if a user is an admin in the current chat."""
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /report command."""
    config = get_report_config()
    if not config.get("is_active"):
        return

    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    # Rate limiting
    now = datetime.now()
    if user.id in report_cooldowns:
        elapsed = (now - report_cooldowns[user.id]).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            wait = int(COOLDOWN_SECONDS - elapsed)
            tmp = await msg.reply_text(f"⚠️ Bitte warte {wait}s bevor du erneut eine Meldung sendest.")
            
            async def delete_after(m, sec):
                await asyncio.sleep(sec)
                try: await m.delete()
                except: pass
            
            asyncio.create_task(delete_after(tmp, 5))
            asyncio.create_task(delete_after(msg, 5))
            return

    if not msg.reply_to_message:
        help_msg = (
            "⚠️ <b>Anleitung: So meldest du eine Nachricht</b>\n\n"
            "1. Gehe zu der Nachricht, die du melden möchtest.\n"
            "2. Nutze die <b>Antwort-Funktion</b> (Reply) auf diese Nachricht.\n"
            "3. Schreibe <code>/report [Grund]</code> (der Grund ist optional).\n\n"
            "Nur wenn du auf eine Nachricht antwortest, wissen die Admins, was gemeldet wurde! 💡"
        )
        await msg.reply_text(help_msg, parse_mode=ParseMode.HTML)
        return

    reported_msg = msg.reply_to_message
    
    # Can't report the bot itself or system messages easily
    if not reported_msg.from_user:
        await msg.reply_text("❌ Diese Nachricht kann nicht gemeldet werden (kein Nutzer zugeordnet).")
        return

    reason = "Kein Grund angegeben."
    if context.args:
        reason = " ".join(context.args)

    try:
        report_id = None
        with flask_app.app_context():
            # Save report to DB
            new_report = ReportedMessage(
                reporter_id=user.id,
                reported_user_id=reported_msg.from_user.id,
                reported_message_id=reported_msg.message_id,
                chat_id=chat.id,
                reason=reason,
                status='pending'
            )
            db.session.add(new_report)
            db.session.commit()
            report_id = new_report.id
            
            # Post to Admin Channel/Topic if configured
            target_chat = config.get("target_chat_id")
            if target_chat:
                target_topic = config.get("target_topic_id")
                
                # Format notification
                rep_name = html.escape(user.first_name)
                target_user = reported_msg.from_user
                target_name = html.escape(target_user.first_name)
                esc_reason = html.escape(reason)
                chat_title = html.escape(chat.title or "Privat")
                
                # Chat link construction (stripped -100 for public/supergroup links)
                chat_id_str = str(chat.id)
                link_id = chat_id_str[4:] if chat_id_str.startswith("-100") else chat_id_str

                report_text = (
                    f"🚨 <b>NEUE MELDUNG (ID: {report_id})</b> 🚨\n\n"
                    f"👤 <b>Melder:</b> {rep_name} (ID: <code>{user.id}</code>)\n"
                    f"👤 <b>Beschuldigter:</b> {target_name} (ID: <code>{target_user.id}</code>)\n"
                    f"💬 <b>Grund:</b> {esc_reason}\n"
                    f"📍 <b>Wo:</b> {chat_title}\n\n"
                    f"🔗 <a href='https://t.me/c/{link_id}/{reported_msg.message_id}'>Zur Nachricht springen</a>"
                )
                
                # Admin action buttons
                keyboard = [
                    [
                        InlineKeyboardButton("🗑️ Löschen", callback_data=f"rep_del_{report_id}"),
                        InlineKeyboardButton("⚠️ Verwarnen", callback_data=f"rep_warn_{report_id}")
                    ],
                    [
                        InlineKeyboardButton("🚫 Bannen", callback_data=f"rep_ban_{report_id}"),
                        InlineKeyboardButton("✅ Erledigt", callback_data=f"rep_ok_{report_id}")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                try:
                    await context.bot.send_message(
                        chat_id=target_chat,
                        text=report_text,
                        message_thread_id=target_topic if target_topic else None,
                        parse_mode=ParseMode.HTML,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Fehler beim Senden der Report-Benachrichtigung an {target_chat}: {e}")

            # Update cooldown
            report_cooldowns[user.id] = now

            # Confirmation to user (and delete after 5s)
            conf = await msg.reply_text("✅ Danke für deine Meldung. Die Administratoren wurden informiert.")
            
            async def delete_messages():
                await asyncio.sleep(5)
                try: await msg.delete() # Delete the /report command message
                except: pass
                try: await conf.delete() # Delete the confirmation
                except: pass
            
            asyncio.create_task(delete_messages())

    except Exception as e:
        logger.error(f"Fehler in report_command: {e}")
        await msg.reply_text("❌ Ein Fehler ist aufgetreten. Bitte versuche es später erneut.")

async def handle_report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks on report notifications."""
    query = update.callback_query
    data = query.data
    admin_user = query.from_user
    
    if not data.startswith("rep_"):
        return
        
    parts = data.split("_")
    if len(parts) < 3: return
    
    action = parts[1] # del, warn, ban, ok
    report_id = int(parts[2])
    
    await query.answer()
    
    try:
        with flask_app.app_context():
            report = ReportedMessage.query.get(report_id)
            if not report:
                await query.edit_message_text("❌ Diese Meldung existiert nicht mehr in der Datenbank.")
                return
                
            if report.status != 'pending' and action != 'ok':
                await query.answer(f"Meldung wurde bereits als '{report.status}' markiert.", show_alert=True)
                return

            target_uid = report.reported_user_id
            chat_id = report.chat_id
            msg_id = report.reported_message_id
            
            result_text = ""
            
            if action == "del":
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    result_text = "🗑️ Nachricht wurde gelöscht."
                except Exception as e:
                    result_text = f"❌ Fehler beim Löschen: {e}"
                report.status = 'resolved'
                
            elif action == "warn":
                # Logic to add warning to DB
                warning_reason = f"Meldung {report_id} akzeptiert: {report.reason}"
                warn = IDFinderWarning(
                    telegram_user_id=target_uid,
                    reason=warning_reason,
                    admin_id=admin_user.id,
                    timestamp=datetime.utcnow()
                )
                db.session.add(warn)
                
                # Also delete message for safety
                try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except: pass
                
                result_text = "⚠️ Nutzer wurde verwarnt & Nachricht gelöscht."
                report.status = 'resolved'
                
            elif action == "ban":
                try:
                    await context.bot.ban_chat_member(chat_id=chat_id, user_id=target_uid)
                    # Also delete
                    try: await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                    except: pass
                    result_text = "🚫 Nutzer wurde verbannt & Nachricht gelöscht."
                except Exception as e:
                    result_text = f"❌ Fehler beim Bannen: {e}"
                report.status = 'resolved'
                
            elif action == "ok":
                result_text = "✅ Meldung wurde als erledigt/ignoriert markiert."
                report.status = 'dismissed'
                
            db.session.commit()
            
            # Get original text to preserve info
            orig_text = query.message.text_html
            
            # Update the admin notification message
            new_text = (
                f"{orig_text}\n\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🛠️ <b>Aktion:</b> {result_text}\n"
                f"👤 <b>Admin:</b> {admin_user.mention_html()}"
            )
            await query.edit_message_text(text=new_text, parse_mode=ParseMode.HTML, reply_markup=None)
            
    except Exception as e:
        logger.error(f"Fehler in handle_report_callback: {e}")
        await query.answer("Kritischer Systemfehler.", show_alert=True)

def get_handlers():
    return [
        CommandHandler("report", report_command),
        CallbackQueryHandler(handle_report_callback, pattern="^rep_")
    ]

if __name__ == "__main__":
    logger.error("Dieses Modul läuft nur via main_bot.py")
