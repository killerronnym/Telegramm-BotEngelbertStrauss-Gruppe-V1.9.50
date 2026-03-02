import os
import sys
import asyncio
from telegram import Bot

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from shared_bot_utils import get_birthday_settings, get_db_url

async def send_announcement():
    settings = get_birthday_settings()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    chat_id = settings.get('target_chat_id', '').strip()
    topic_id = settings.get('target_topic_id', '').strip()
    
    if not chat_id:
        print("Error: No target_chat_id set in birthday settings.")
        return

    # Auto-fix prefix
    if not chat_id.startswith('-'):
        if chat_id.startswith('100'): chat_id = f"-{chat_id}"
        else: chat_id = f"-100{chat_id}"

    announcement = (
        "📣 <b>Update: Der Geburtsags-Bot ist bereit!</b> 🎂✨\n\n"
        "Ab sofort könnt ihr euren Geburtstag direkt über den Bot registrieren! Wir feiern eure Ehrentage dann gemeinsam in der Gruppe.\n\n"
        "<b>So funktioniert es:</b>\n"
        "1️⃣ Nutzt den Befehl <code>/gb</code> oder <code>/geburtstag</code>.\n"
        "2️⃣ Schreibt mir euer Datum (z.B. <code>15.08.</code>).\n"
        "3️⃣ <i>Optional:</i> Ihr könnt auch das Jahr angeben (z.B. <code>15.08.1990</code>), dann berechnet der Bot euer Alter!\n\n"
        "Ich freue mich darauf, mit euch zu feiern! 🎉"
    )

    bot = Bot(token=token)
    kwargs = {"chat_id": chat_id, "text": announcement, "parse_mode": "HTML"}
    if topic_id and topic_id.isdigit():
        kwargs["message_thread_id"] = int(topic_id)

    try:
        await bot.send_message(**kwargs)
        print(f"Announcement sent successfully to {chat_id}")
    except Exception as e:
        print(f"Error sending announcement: {e}")

if __name__ == "__main__":
    asyncio.run(send_announcement())
