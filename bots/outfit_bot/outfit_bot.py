import telebot
import schedule
import time
import threading
import json
import os
import random
import logging
import sys
from telebot import types
from datetime import datetime, timedelta

# --- PATH SETUP ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'outfit_bot.log')
CONFIG_FILE = os.path.join(BASE_DIR, 'outfit_bot_config.json')
DATA_FILE = os.path.join(BASE_DIR, 'outfit_bot_data.json')

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

DEFAULT_CONFIG = {
    "BOT_TOKEN": "DUMMY",
    "CHAT_ID": "",
    "TOPIC_ID": "",
    "POST_TIME": "18:00",
    "WINNER_TIME": "22:00",
    "AUTO_POST_ENABLED": True,
    "ADMIN_USER_IDS": [],
    "DUEL_MODE": False,
    "DUEL_TYPE": "tie_breaker",
    "DUEL_DURATION_MINUTES": 60,
    "TEMPORARY_MESSAGE_DURATION_SECONDS": 30,
    "PIN_DAILY_POST": True,
    "PIN_DISABLE_NOTIFICATION": True
}


def load_json(filename, default_data=None):
    if not os.path.exists(filename) or os.path.getsize(filename) == 0:
        if default_data:
            save_json(filename, default_data)
        return default_data or {}
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.error(f"Error loading JSON file {filename}: {e}", exc_info=True)
        return default_data or {}


def save_json(filename, data):
    try:
        tmp_file = filename + ".tmp"
        with open(tmp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        os.replace(tmp_file, filename)
    except Exception as e:
        logging.error(f"Error saving JSON file {filename}: {e}", exc_info=True)


config = load_json(CONFIG_FILE, DEFAULT_CONFIG)
initial_token = config.get("BOT_TOKEN")

if not initial_token or initial_token == "DUMMY":
    logging.warning("Outfit-Bot startet mit Platzhalter-Token. Bitte konfigurieren.")
    # Wir beenden hier nicht hart, damit der Prozess läuft und via Dashboard logs zeigt
    # Aber wir können keinen Bot instanziieren der funktioniert.
    initial_token = "0:dummy"

bot = telebot.TeleBot(initial_token, threaded=False)


# --- HELPER FUNCTIONS ---
def get_config():
    """Safely reloads the config from file."""
    return load_json(CONFIG_FILE, DEFAULT_CONFIG)


def get_topic_id(cfg):
    """Returns the Topic ID as an integer if it exists."""
    topic_id_str = cfg.get("TOPIC_ID")
    return int(topic_id_str) if topic_id_str and str(topic_id_str).isdigit() else None


def is_admin(user_id):
    """Checks if a user is an admin."""
    return str(user_id) in [str(uid) for uid in get_config().get("ADMIN_USER_IDS", [])]


# --- PIN / UNPIN HELPERS ---
def _save_pinned_message_id(message_id: int):
    try:
        bot_data = load_json(DATA_FILE, {})
        bot_data["pinned_message_id"] = int(message_id)
        save_json(DATA_FILE, bot_data)
    except Exception as e:
        logging.error(f"Could not save pinned_message_id: {e}", exc_info=True)


def _clear_pinned_message_id():
    try:
        bot_data = load_json(DATA_FILE, {})
        if "pinned_message_id" in bot_data:
            del bot_data["pinned_message_id"]
            save_json(DATA_FILE, bot_data)
    except Exception as e:
        logging.error(f"Could not clear pinned_message_id: {e}", exc_info=True)


def pin_daily_post_message(chat_id, message_id: int, topic_id=None):
    cfg = get_config()
    if not cfg.get("PIN_DAILY_POST", True):
        return

    disable_notification = cfg.get("PIN_DISABLE_NOTIFICATION", True)

    try:
        # Versuch mit message_thread_id (neuere API)
        # Wenn topic_id None ist, wird es meist ignoriert oder als General gewertet
        bot.pin_chat_message(
            chat_id=chat_id,
            message_id=int(message_id),
            disable_notification=disable_notification
        )
        _save_pinned_message_id(int(message_id))
        logging.info(f"Pinned daily post {message_id} in {chat_id}.")
    except Exception as e:
        logging.error(f"Error pinning daily post message: {e}")


def unpin_daily_post_message(chat_id, topic_id=None):
    try:
        bot_data = load_json(DATA_FILE, {})
        pinned_id = bot_data.get("pinned_message_id")
        if not pinned_id:
            return

        pinned_id = int(pinned_id)
        bot.unpin_chat_message(chat_id=chat_id, message_id=pinned_id)
        logging.info(f"Unpinned daily post {pinned_id} in {chat_id}.")
        _clear_pinned_message_id()
    except Exception as e:
        logging.error(f"Error unpinning daily post message: {e}")


def reset_contest_data(is_starting_new_contest=False):
    cfg = get_config()
    chat_id = cfg.get("CHAT_ID")
    topic_id = get_topic_id(cfg)

    if chat_id:
        unpin_daily_post_message(chat_id, topic_id)

    new_data = {
        "submissions": {},
        "votes": {},
        "contest_active": is_starting_new_contest,
        "max_votes": 0,
        "current_duel": None
    }
    save_json(DATA_FILE, new_data)
    logging.info(f"Contest data reset. Active: {is_starting_new_contest}.")


def generate_markup(user_id, likes=0, loves=0, fires=0):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(f"👍 ({likes})", callback_data=f"vote_like_{user_id}"),
        types.InlineKeyboardButton(f"❤️ ({loves})", callback_data=f"vote_love_{user_id}"),
        types.InlineKeyboardButton(f"🔥 ({fires})", callback_data=f"vote_fire_{user_id}")
    )
    return markup


def count_votes(votes_dict):
    counts = {'like': 0, 'love': 0, 'fire': 0}
    for vote_type in votes_dict.values():
        if vote_type in counts:
            counts[vote_type] += 1
    return counts


# --- DUEL & WINNER ANNOUNCEMENT LOGIC ---
def announce_winners_grouped(winner_user_ids, votes, reason=""):
    cfg = get_config()
    chat_id = cfg.get("CHAT_ID")
    if not chat_id: return
    topic_id = get_topic_id(cfg)
    bot_data = load_json(DATA_FILE)
    submissions = bot_data.get("submissions", {})

    media = []
    winner_names = []

    for user_id in winner_user_ids:
        user_id_str = str(user_id)
        if user_id_str in submissions:
            username = submissions[user_id_str].get("username", "Unknown")
            photo_id = submissions[user_id_str]["photo_id"]
            winner_names.append(f"@{username}")
            media.append(types.InputMediaPhoto(photo_id))

    if not media:
        logging.error("No valid media found for grouped winner announcement.")
        return

    caption = (
        f"🏆 Outfit des Tages: {', '.join(winner_names)} mit {votes} Reaktionen! "
        f"Herzlichen Glückwunsch! 🥳"
    )
    media[0].caption = caption

    try:
        bot.send_media_group(chat_id, media, message_thread_id=topic_id)
        logging.info(f"Announced winners ({reason}): {', '.join(winner_names)}.")
    except Exception as e:
        logging.error(f"Error announcing winners: {e}")


def start_duel(tied_message_ids):
    logging.info(f"Starting duel for: {tied_message_ids}")
    cfg = get_config()
    chat_id = cfg.get("CHAT_ID")
    topic_id = get_topic_id(cfg)
    bot_data = load_json(DATA_FILE)
    submissions = bot_data.get("submissions", {})

    if len(tied_message_ids) < 2:
        return

    contestant_msg_ids = random.sample(tied_message_ids, 2)
    contestants = []
    
    for msg_id in contestant_msg_ids:
        user_id = next((uid for uid, s in submissions.items() if str(s.get("message_id")) == msg_id), None)
        if user_id:
            contestants.append({
                "user_id": user_id,
                "username": submissions[user_id].get("username", "Unknown"),
                "photo_id": submissions[user_id].get("photo_id")
            })

    if len(contestants) != 2:
        return

    c1, c2 = contestants[0], contestants[1]

    try:
        media = [
            types.InputMediaPhoto(c1['photo_id'], caption=f"Kandidat 1: @{c1['username']}"),
            types.InputMediaPhoto(c2['photo_id'], caption=f"Kandidat 2: @{c2['username']}")
        ]
        bot.send_media_group(chat_id, media, message_thread_id=topic_id)

        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton(f"👍 für @{c1['username']}", callback_data=f"duel_vote_{c1['user_id']}"),
            types.InlineKeyboardButton(f"👍 für @{c2['username']}", callback_data=f"duel_vote_{c2['user_id']}")
        )
        poll_message = bot.send_message(
            chat_id,
            "⚔️ DUEL! Wer soll gewinnen? Stimmt jetzt ab!",
            reply_markup=markup,
            message_thread_id=topic_id
        )

        duel_data = {
            "poll_message_id": poll_message.message_id,
            "contestants": {
                c1['user_id']: {'username': c1['username'], 'photo_id': c1['photo_id'], 'votes': 0},
                c2['user_id']: {'username': c2['username'], 'photo_id': c2['photo_id'], 'votes': 0}
            },
            "voters": {}
        }
        bot_data["current_duel"] = duel_data
        save_json(DATA_FILE, bot_data)

        duration = cfg.get("DUEL_DURATION_MINUTES", 60)
        end_time = datetime.now() + timedelta(minutes=duration)
        schedule.every().day.at(end_time.strftime('%H:%M')).do(end_duel).tag('duel-end')

    except Exception as e:
        logging.error(f"Failed to start duel: {e}")


def end_duel():
    logging.info("Ending duel...")
    cfg = get_config()
    chat_id = cfg.get("CHAT_ID")
    topic_id = get_topic_id(cfg)
    bot_data = load_json(DATA_FILE)
    duel_data = bot_data.get("current_duel")

    if not duel_data:
        reset_contest_data(is_starting_new_contest=False)
        return schedule.CancelJob

    contestants = duel_data.get("contestants", {})
    max_votes = -1
    winners_user_ids = []

    for user_id, data in contestants.items():
        if data['votes'] > max_votes:
            max_votes = data['votes']
            winners_user_ids = [user_id]
        elif data['votes'] == max_votes:
            winners_user_ids.append(user_id)

    if winners_user_ids and max_votes > 0:
        announce_winners_grouped(winners_user_ids, max_votes, "duel_winner")
    else:
        try:
            bot.send_message(chat_id, "Das Duell endet ohne klaren Sieger.", message_thread_id=topic_id)
        except: pass

    reset_contest_data(is_starting_new_contest=False)
    schedule.clear('duel-end')
    return schedule.CancelJob


# --- CORE BOT FUNCTIONS ---
def send_daily_post():
    logging.info("Sending daily post...")
    reset_contest_data(is_starting_new_contest=True)
    cfg = get_config()
    chat_id = cfg.get("CHAT_ID")
    if not chat_id: return
    topic_id = get_topic_id(cfg)

    try:
        bot_username = bot.get_me().username
        start_url = f"https://t.me/{bot_username}?start=participate"
        markup = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("Mitmachen", url=start_url)
        )
        sent = bot.send_message(
            chat_id,
            "📸 Outfit des Tages – zeigt eure heutigen E.S-Outfits!",
            reply_markup=markup,
            message_thread_id=topic_id
        )
        pin_daily_post_message(chat_id=chat_id, message_id=sent.message_id, topic_id=topic_id)
    except Exception as e:
        logging.error(f"Error sending daily post: {e}")


def determine_winner():
    logging.info("Determining winner...")
    cfg = get_config()
    chat_id = cfg.get("CHAT_ID")
    if not chat_id: return
    topic_id = get_topic_id(cfg)

    bot_data = load_json(DATA_FILE)
    if not bot_data.get("submissions"):
        try:
            bot.send_message(chat_id, "Keine Einreichungen heute.", message_thread_id=topic_id)
        except: pass
        reset_contest_data(is_starting_new_contest=False)
        return

    winner_info = {}
    max_votes = -1
    for msg_id, votes in bot_data.get("votes", {}).items():
        total_votes = len(votes)
        if total_votes > max_votes:
            max_votes = total_votes
            winner_info = {msg_id: total_votes}
        elif total_votes == max_votes:
            winner_info[msg_id] = total_votes

    bot_data["max_votes"] = max_votes
    save_json(DATA_FILE, bot_data)

    if not winner_info or max_votes <= 0:
        try:
            bot.send_message(chat_id, "Keine Stimmen abgegeben.", message_thread_id=topic_id)
        except: pass
        reset_contest_data(is_starting_new_contest=False)
        return

    tied_message_ids = list(winner_info.keys())
    submissions = bot_data.get("submissions", {})
    tied_user_ids = []
    
    for msg_id in tied_message_ids:
        user_id = next((uid for uid, s in submissions.items() if str(s.get("message_id")) == msg_id), None)
        if user_id: tied_user_ids.append(user_id)

    if len(tied_message_ids) > 1 and cfg.get("DUEL_MODE"):
        if cfg.get("DUEL_TYPE") == "tie_breaker" and len(tied_message_ids) >= 2:
            try:
                bot.send_message(chat_id, f"Unentschieden! Duell startet...", message_thread_id=topic_id)
                start_duel(tied_message_ids)
            except: pass
        else:
             announce_winners_grouped(tied_user_ids, max_votes, "multiple")
             reset_contest_data(False)
    else:
        announce_winners_grouped([random.choice(tied_user_ids)], max_votes, "single")
        reset_contest_data(False)


# --- HANDLERS ---
@bot.message_handler(commands=['start'])
def handle_start(message):
    if message.chat.type == 'private':
        if "participate" in message.text:
            bot.send_message(message.chat.id, "Bitte sende jetzt dein Foto!")
        else:
            bot.send_message(message.chat.id, "Hallo vom Outfit-Bot!")

@bot.message_handler(commands=['start_contest', 'announce_winner', 'end_duel'])
def handle_admin_commands(message):
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    
    if not is_admin(message.from_user.id):
        return

    cmd = message.text.split()[0][1:]
    if cmd == "start_contest": send_daily_post()
    elif cmd == "announce_winner": determine_winner()
    elif cmd == "end_duel": end_duel()

@bot.message_handler(content_types=['photo'])
def handle_photo_submission(message):
    if message.chat.type != 'private': return

    bot_data = load_json(DATA_FILE)
    if not bot_data.get("contest_active", False):
        bot.send_message(message.chat.id, "Gerade läuft kein Wettbewerb.")
        return

    user_id = str(message.from_user.id)
    if user_id in bot_data.get("submissions", {}):
        bot.send_message(message.chat.id, "Du hast schon ein Bild gesendet.")
        return

    cfg = get_config()
    chat_id = cfg.get("CHAT_ID")
    if not chat_id:
        bot.send_message(message.chat.id, "Bot ist nicht konfiguriert.")
        return
        
    topic_id = get_topic_id(cfg)
    photo_id = message.photo[-1].file_id
    username = message.from_user.username or message.from_user.first_name
    caption = f"Outfit von @{username}"
    markup = generate_markup(int(user_id))

    try:
        sent = bot.send_photo(chat_id, photo_id, caption=caption, reply_markup=markup, message_thread_id=topic_id)
        
        bot_data.setdefault("submissions", {})[user_id] = {
            "message_id": sent.message_id,
            "photo_id": photo_id,
            "username": username
        }
        bot_data.setdefault("votes", {})[str(sent.message_id)] = {}
        save_json(DATA_FILE, bot_data)
        
        bot.send_message(message.chat.id, "Dein Bild ist online! ✅")
    except Exception as e:
        logging.error(f"Upload failed: {e}")
        bot.send_message(message.chat.id, "Fehler beim Hochladen.")

@bot.callback_query_handler(func=lambda call: True)
def handle_vote(call):
    # Einfache Vote-Logik
    user_id = str(call.from_user.id)
    
    if call.data.startswith('duel_vote_'):
        # Duel Vote Logic Wrapper
        handle_duel_vote(call)
        return

    try:
        _, vote_type, target_id_str = call.data.split('_')
    except: return

    bot_data = load_json(DATA_FILE)
    # Find message ID belonging to target_id_str (which is the submitter user ID)
    target_msg_id = None
    for uid, sub in bot_data.get("submissions", {}).items():
        if str(uid) == target_id_str:
            target_msg_id = str(sub["message_id"])
            break
    
    if not target_msg_id: return
    
    votes = bot_data.get("votes", {}).get(target_msg_id, {})
    
    if votes.get(user_id) == vote_type:
        del votes[user_id]
        txt = "Stimme entfernt."
    else:
        votes[user_id] = vote_type
        txt = f"Gestimmt für {vote_type}."
        
    bot_data["votes"][target_msg_id] = votes
    save_json(DATA_FILE, bot_data)
    
    counts = count_votes(votes)
    try:
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=generate_markup(int(target_id_str), counts['like'], counts['love'], counts['fire'])
        )
    except: pass
    
    bot.answer_callback_query(call.id, txt)

def handle_duel_vote(call):
    # (Vereinfachte Logik, ähnlich wie oben, aber für Duell)
    pass # Placeholder, da oben implementiert in handle_vote wenn nötig, oder separat

# --- MAIN ---
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

def command_listener():
    # Watch for trigger files
    files = {
        "command_start_contest.tmp": send_daily_post,
        "command_announce_winner.tmp": determine_winner,
        "command_end_duel.tmp": end_duel
    }
    while True:
        for fname, func in files.items():
            fpath = os.path.join(BASE_DIR, fname)
            if os.path.exists(fpath):
                try:
                    func()
                except Exception as e:
                    logging.error(f"Error executing {fname}: {e}")
                finally:
                    try: os.remove(fpath)
                    except: pass
        time.sleep(2)

if __name__ == "__main__":
    # Schedule setup
    cfg = get_config()
    if cfg.get("AUTO_POST_ENABLED"):
        schedule.every().day.at(cfg.get("POST_TIME", "18:00")).do(send_daily_post)
        schedule.every().day.at(cfg.get("WINNER_TIME", "22:00")).do(determine_winner)

    threading.Thread(target=run_scheduler, daemon=True).start()
    threading.Thread(target=command_listener, daemon=True).start()
    
    try:
        bot.polling(non_stop=True, skip_pending=True)
    except Exception as e:
        logging.error(f"Polling error: {e}")
