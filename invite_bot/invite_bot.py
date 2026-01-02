import logging
import os
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, ChatInviteLink
from telegram.helpers import escape_markdown
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

# --- Setup ------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,  # Changed back to INFO for production, use DEBUG for detailed local debugging
)
logger = logging.getLogger(__name__)

# --- Dateien & Speicher -----------------------------------------
# Pfade relativ zum Ausführungsort (was das invite_bot Verzeichnis sein sollte)
BOT_SETTINGS_CONFIG_FILE = 'invite_bot_config.json'  # CORRECTED FILE NAME
USER_INTERACTIONS_LOG_FILE = 'user_interactions.log'

# Data Ordner liegt eine Ebene höher
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = Path(os.path.join(PROJECT_ROOT, "data"))
DATA_DIR.mkdir(exist_ok=True)
PROFILES_FILE = DATA_DIR / "profiles.json"

FREIWILLIG_HINT = "_Diese Frage kannst du mit **nein** überspringen\\._"
MAX_TEXT_LENGTH = 180  # Maximale Zeichenlänge für Freitextfelder


def log_user_interaction(user_id: int, question: str, answer: str):
    """Loggt die Eingaben des Benutzers in eine separate Datei."""
    with open(USER_INTERACTIONS_LOG_FILE, 'a', encoding='utf-8') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] UserID: {user_id}\n  Frage: {question}\n  Antwort: {answer}\n\n")


def load_json(file_path, default_data):
    if not Path(file_path).exists() or Path(file_path).stat().st_size == 0:
        return default_data
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default_data


def load_bot_settings_config():
    default = {
        "is_enabled": False,
        "bot_token": "",
        "main_chat_id": "",
        "topic_id": "",
        "link_ttl_minutes": 15,
        "repost_profile_for_existing_members": True
    }
    return load_json(BOT_SETTINGS_CONFIG_FILE, default)


def is_valid(value: str) -> bool:
    return value and value.strip().lower() != "nein"


def _load_all_profiles():
    if not PROFILES_FILE.exists():
        return {}
    try:
        with PROFILES_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Fehler beim Laden der Profile: {e}")
        return {}


def _save_all_profiles(data: dict):
    try:
        with PROFILES_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Profile: {e}")


def save_profile(user_id: int, profile: dict):
    data = _load_all_profiles()
    data[str(user_id)] = profile
    _save_all_profiles(data)


def load_profile(user_id: int):
    return _load_all_profiles().get(str(user_id))


def remove_profile(user_id: int):
    data = _load_all_profiles()
    if str(user_id) in data:
        del data[str(user_id)]
        _save_all_profiles(data)


# --- States -----------------------------------------------------
ASK_NAME, ASK_AGE, ASK_STATE, ASK_PHOTO, ASK_HOBBIES, ASK_INSTAGRAM, ASK_OTHER, ASK_SEXUALITY, ASK_RULES = range(9)
user_data_temp = {}


async def reply_with_developer_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "Vielen Dank\\. Ich wurde entwickelt von @pup\\_Rinno\\_cgn",
            parse_mode="MarkdownV2"
        )


# ✅ /datenschutz -------------------------------------------------
async def datenschutz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔐 *Datenschutz & Datenverarbeitung*\n\n"
        "Dieser Bot hilft dir, in die *Engelbert—Strauss Gruppe* beizutreten, indem du vorher einen kurzen Steckbrief ausfüllst\\.\n\n"
        "✅ *Pflichtangaben:*\n"
        "• Name\n"
        "• Alter\n"
        "• Bundesland\n"
        "• Foto \\(als normales Foto, kein Dokument\\)\n"
        "• Bestätigung der Regeln \\(„OK“\\)\n\n"
        "➕ *Freiwillige Angaben \\(mit „nein“ überspringen\\):*\n"
        "• Hobbys / Interessen\n"
        "• Social Media\n"
        "• Sonstiges\n"
        "• Sexualität\n\n"
        "🧠 *Wofür werden die Daten genutzt\\?*\n"
        "• Damit du nach dem Ausfüllen *automatisch einen Einladungslink* bekommst\\.\n"
        "• Sobald du der Hauptgruppe beitrittst, wird dein Steckbrief *automatisch in der Gruppe gepostet*\\.\n\n"
        "🗑️ *Speicherung & Löschung:*\n"
        "• Die Angaben werden nur so lange gespeichert, bis dein Beitritt genehmigt wurde und der Steckbrief gepostet ist\\.\n"
        "• Danach werden die intern gespeicherten Profildaten wieder gelöscht\\.\n"
        "• Das Foto wird über Telegram verarbeitet \\(es wird nur die Telegram *file\\_id* genutzt, um es zu posten\\)\\.\n\n"
        "📌 *Wichtig: Gruppenverlauf*\n"
        "Der Steckbrief\\-Post bleibt im Chatverlauf sichtbar, solange er nicht von Admins gelöscht wird\\.\n\n"
        "📊 *Analyse / Aktivitätsauswertung*\n"
        "In der Gruppe kann zusätzlich ein Analyse\\-Bot genutzt werden, um Aktivität/Inaktivität zu erkennen\\.\n"
        "Daten können dabei bis zu *1 Jahr* gespeichert und danach gelöscht werden\\.\n\n"
        "📄 *Telegram*\n"
        "Zusätzlich gelten die Telegram\\-Regeln und die Telegram\\-Datenschutzerklärung\\.\n\n"
        "👤 *Kontakt*\n"
        "Entwickler: @pup\\_Rinno\\_cgn\n"
        "Bei Fragen kannst du mir jederzeit schreiben 😊"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


# --- Commands ---------------------------------------------------
async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👋 *Hey und herzlich willkommen\\!* \n\n"
        "Du bist hier, weil du in unsere *Engelbert—Strauss Gruppe* möchtest 👷‍♂️🦺\n\n"
        "Damit wir wissen, wer du bist und dich richtig freischalten können, hilft dir dieser Bot dabei, "
        "einen kurzen Steckbrief auszufüllen 📋\n\n"
        "➡️ Das dauert nur *1–2 Minuten\\!* \n"
        "➡️ Danach bekommst du *automatisch den Einladungslink* zur Gruppe 🔗\n\n"
        "🔐 Wenn du vorher wissen willst, was mit deinen Daten passiert: */datenschutz*\n\n"
        "Das hier ist *kein Spam*, sondern eine kleine Sicherheitsabfrage ✅\n\n"
        "👉 *Schreibe jetzt einfach /letsgo, um zu starten\\!*"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


# ✅ /letsgo startet Formular + Ban/Kick-Check
async def start_form(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    config = load_bot_settings_config()
    GROUP_ID = int(config.get("main_chat_id", 0)) if config.get("main_chat_id") else 0

    if not GROUP_ID:
        await update.message.reply_text("⚠️ Fehler: Die Gruppen-ID ist nicht konfiguriert\\.", parse_mode="MarkdownV2")
        return ConversationHandler.END

    # ✅ Vorab prüfen: ist der User ggf. gesperrt (kicked/banned)?
    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_ID, user_id=user.id)

        # In Telegram bedeutet "kicked" = gesperrt/gebanned.
        if getattr(member, "status", "") == "kicked":
            msg = (
                "⚠️ *Freischaltung aktuell nicht möglich\\.*\n\n"
                "Für deinen Account kann im Moment kein Gruppenlink erstellt werden\\.\n"
                "Bitte wende dich an einen Administrator, damit das kurz geprüft und ggf\\. freigeschaltet werden kann 😊\n\n"
                "👉 Admin: [@didinils](https://t.me/didinils)"
            )
            await update.message.reply_text(msg, parse_mode="MarkdownV2", disable_web_page_preview=True)
            return ConversationHandler.END

    except TelegramError:
        # Falls Telegram bei Sonderfällen meckert: nicht blockieren, einfach normal weiter.
        pass
    except Exception as e:
        logger.error(f"[start_form] Fehler bei Ban-Check für User {user.id}: {e}", exc_info=True)
        pass

    await update.message.reply_text("Wie ist dein Name? Es reicht dein Vorname\\.", parse_mode="MarkdownV2")
    return ASK_NAME


# --- Formular Schritte ---
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    answer = update.message.text.strip()
    log_user_interaction(user.id, "Name", answer)
    user_data_temp[user.id] = {
        "name": answer,
        "telegram_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
    }
    await update.message.reply_text("Wie alt bist du? \\(zwischen 10 und 100\\)", parse_mode="MarkdownV2")
    return ASK_AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    age_text = update.message.text.strip()
    if not age_text.isdigit() or not 10 <= int(age_text) <= 100:
        await update.message.reply_text("Bitte gib dein Alter als Zahl zwischen 10 und 100 ein\\.", parse_mode="MarkdownV2")
        return ASK_AGE
    log_user_interaction(update.message.from_user.id, "Alter", age_text)
    user_data_temp[update.message.from_user.id]["age"] = age_text
    await update.message.reply_text("Aus welchem Bundesland kommst du? \\(z\\.B\\. NRW, Bayern, Berlin …\\)", parse_mode="MarkdownV2")
    return ASK_STATE


async def get_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    answer = update.message.text.strip()
    log_user_interaction(user.id, "Bundesland", answer)
    user_data_temp[user.id]["state"] = answer
    await update.message.reply_text("Bitte sende ein *normales Foto* von dir \\(kein Dokument\\)\\.", parse_mode="MarkdownV2")
    return ASK_PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not update.message.photo:
        await update.message.reply_text("Bitte sende ein Foto, kein Dokument\\.", parse_mode="MarkdownV2")
        return ASK_PHOTO
    log_user_interaction(user_id, "Foto", "Foto erhalten")
    user_data_temp[user_id]["photo_file_id"] = update.message.photo[-1].file_id
    await update.message.reply_text(f"🎯 Was sind deine Hobbys oder Interessen?\n\n{FREIWILLIG_HINT}", parse_mode="MarkdownV2")
    return ASK_HOBBIES


async def get_hobbies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(f"Ups, dein Text ist zu lang\\! Bitte versuche es mit maximal {MAX_TEXT_LENGTH} Zeichen noch einmal\\.", parse_mode="MarkdownV2")
        return ASK_HOBBIES
    log_user_interaction(user_id, "Hobbys", text)
    if is_valid(text):
        user_data_temp[user_id]["hobbies"] = text
    await update.message.reply_text(f"📱 Trage hier deinen Instagram oder einen anderen Social Media Account ein:\n\n{FREIWILLIG_HINT}", parse_mode="MarkdownV2")
    return ASK_INSTAGRAM


async def get_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(f"Ups, dein Text ist zu lang\\! Bitte versuche es mit maximal {MAX_TEXT_LENGTH} Zeichen noch einmal\\.", parse_mode="MarkdownV2")
        return ASK_INSTAGRAM
    log_user_interaction(user_id, "Instagram", text)
    if is_valid(text):
        user_data_temp[user_id]["instagram"] = text
    await update.message.reply_text(f"💬 Möchtest du noch etwas über dich sagen?\n\n{FREIWILLIG_HINT}", parse_mode="MarkdownV2")
    return ASK_OTHER


async def get_other(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(f"Ups, dein Text ist zu lang\\! Bitte versuche es mit maximal {MAX_TEXT_LENGTH} Zeichen noch einmal\\.", parse_mode="MarkdownV2")
        return ASK_OTHER
    log_user_interaction(user_id, "Sonstiges", text)
    if is_valid(text):
        user_data_temp[user_id]["other"] = text
    await update.message.reply_text(f"🏳️‍🌈 Wie ist deine Sexualität?\n\n{FREIWILLIG_HINT}", parse_mode="MarkdownV2")
    return ASK_SEXUALITY


async def get_sexuality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.message.from_user.id
    if len(text) > MAX_TEXT_LENGTH:
        await update.message.reply_text(f"Ups, dein Text ist zu lang\\! Bitte versuche es mit maximal {MAX_TEXT_LENGTH} Zeichen noch einmal\\.", parse_mode="MarkdownV2")
        return ASK_SEXUALITY
    log_user_interaction(user_id, "Sexualität", text)
    if is_valid(text):
        user_data_temp[user_id]["sexuality"] = text

    regeln = (
        "📜 *Bevor du in die Gruppe kommst, lies bitte unsere Regeln:*\n\n"
        "✅ *DOS:*\n"
        "• Respektvoller Umgang\n"
        "• Überwiegend gute Laune 😄\n\n"
        "❌ *DON'TS:*\n"
        "✖️ Beleidigungen\n"
        "✖️ Diskriminierung\n"
        "✖️ Hardcore\\-Inhalte\n"
        "✖️ Blut oder offene Wunden\n"
        "✖️ Inhalte mit Kindern\n"
        "✖️ Inhalte mit Tieren \\(sexuell\\)\n"
        "✖️ Inhalte mit Bezug auf Tod\n"
        "✖️ Exkremente\n\n"
        "_Verstöße werden durch Admins geprüft und bei Wiederholung erfolgt Ausschluss\\._\n\n"
        "👉 *Wenn du einverstanden bist, bestätige mit OK\\.*"
    )
    await update.message.reply_text(regeln, parse_mode="MarkdownV2")
    return ASK_RULES


# --- Willkommensnachricht & Beitritt ---
def format_welcome(profile: dict) -> str:
    def esc(text):
        return escape_markdown(str(text), version=2)

    username = profile.get('username')
    if username:
        user_link = f"[{esc(username)}](tg://user?id={profile.get('telegram_id')})"
    else:
        user_link = esc(profile.get('first_name', 'Unbekannt'))

    join_date_str = datetime.now().strftime('%d\\.%m\\.%Y – %H\\:%M')

    lines = [
        "🎉 *Willkommen in der Gruppe\\!*",
        f"👤 *Name:* {esc(profile.get('name', '-'))}",
        f"🎂 *Alter:* {esc(profile.get('age', '-'))}",
        f"📍 *Bundesland:* {esc(profile.get('state', '-'))}",
        f"🔗 *Telegram:* {user_link}",
    ]
    if is_valid(profile.get("hobbies", "")):
        lines.append(f"🎯 *Hobbys:* {esc(profile['hobbies'])}")
    if is_valid(profile.get("instagram", "")):
        lines.append(f"📱 *Social Media:* {esc(profile['instagram'])}")
    if is_valid(profile.get("other", "")):
        lines.append(f"💬 *Sonstiges:* {esc(profile['other'])}")
    if is_valid(profile.get("sexuality", "")):
        lines.append(f"🏳️‍🌈 *Sexualität:* {esc(profile['sexuality'])}")
    lines.append(f"🕐 *Beigetreten am:* {join_date_str}")
    return "\n".join(lines)


async def _send_profile_to_group(user_id: int, profile: dict, chat_id: int, topic_id: int | None, context: ContextTypes.DEFAULT_TYPE):
    welcome_message = format_welcome(profile)
    try:
        if profile.get("photo_file_id"):
            logger.info(f"[send_profile_to_group] Sende Foto mit Profil für User {user_id} an Gruppe {chat_id}, Topic {topic_id}")
            await context.bot.send_photo(chat_id=chat_id, photo=profile["photo_file_id"], caption=welcome_message, parse_mode="MarkdownV2", message_thread_id=topic_id)
        else:
            logger.info(f"[send_profile_to_group] Sende Textprofil für User {user_id} an Gruppe {chat_id}, Topic {topic_id}")
            await context.bot.send_message(chat_id=chat_id, text=welcome_message, parse_mode="MarkdownV2", message_thread_id=topic_id)
        logger.info(f"[send_profile_to_group] Profil erfolgreich in Gruppe gepostet für User {user_id}")
        return True
    except Exception as e:
        logger.error(f"[send_profile_to_group] Fehler bei Begrüßung in Gruppe/Topic für User {user_id}: {e}", exc_info=True)
        return False


async def get_rules_ok(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if update.message.text.strip().lower() != "ok":
        await update.message.reply_text("Bitte antworte mit *OK*, um den Regeln zuzustimmen\\.", parse_mode="MarkdownV2")
        return ASK_RULES

    # Save profile data
    user_data_temp[user_id]["created_at"] = datetime.utcnow().isoformat()
    save_profile(user_id, user_data_temp[user_id])

    config = load_bot_settings_config()
    GROUP_ID = int(config.get("main_chat_id", 0)) if config.get("main_chat_id") else 0
    TOPIC_ID_STR = config.get("topic_id")
    TOPIC_ID = int(TOPIC_ID_STR) if TOPIC_ID_STR and TOPIC_ID_STR.isdigit() else None
    LINK_TTL_MINUTES = config.get("link_ttl_minutes", 15)
    repost_setting = config.get("repost_profile_for_existing_members", True)

    logger.debug(f"[get_rules_ok] User: {user_id}, GROUP_ID: {GROUP_ID}, TOPIC_ID: {TOPIC_ID}, Repost Setting: {repost_setting}")

    if not GROUP_ID:
        logger.error("GROUP_ID ist nicht konfiguriert oder ungültig.")
        await update.message.reply_text("⚠️ Fehler: Die Gruppen-ID ist nicht konfiguriert\\.", parse_mode="MarkdownV2")
        user_data_temp.pop(user_id, None)
        return ConversationHandler.END

    is_already_member = False
    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        is_already_member = member.status in ['member', 'administrator', 'creator']
        logger.debug(f"[get_rules_ok] User {user_id} member status: {member.status}, is_already_member: {is_already_member}")
    except TelegramError as e:
        logger.debug(f"[get_rules_ok] User {user_id} ist kein aktuelles Mitglied der Gruppe (Fehler: {e}).")
        is_already_member = False
    except Exception as e:
        logger.error(f"[get_rules_ok] Fehler beim Abrufen des Chat-Mitgliedsstatus für User {user_id}: {e}", exc_info=True)
        await update.message.reply_text(f"⚠️ Fehler beim Überprüfen des Mitgliederstatus\\: {escape_markdown(str(e), version=2)}", parse_mode="MarkdownV2")
        user_data_temp.pop(user_id, None)
        return ConversationHandler.END

    if is_already_member and repost_setting:
        logger.info(f"[get_rules_ok] User {user_id} ist bereits Mitglied und Reposting ist aktiviert. Sende Profil.")
        profile = load_profile(user_id)
        if profile:
            success = await _send_profile_to_group(user_id, profile, GROUP_ID, TOPIC_ID, context)
            if success:
                await update.message.reply_text("✅ Dein Steckbrief wurde erfolgreich in der Gruppe gepostet\\.", parse_mode="MarkdownV2")
            else:
                await update.message.reply_text("⚠️ Fehler beim Posten des Steckbriefs in der Gruppe\\.", parse_mode="MarkdownV2")
            remove_profile(user_id)  # Profil sofort löschen, wenn schon gepostet
        else:
            logger.error(f"[get_rules_ok] Profil für User {user_id} konnte nicht geladen werden, obwohl es gespeichert sein sollte.")
            await update.message.reply_text("⚠️ Ein interner Fehler ist aufgetreten\\. Dein Steckbrief konnte nicht gefunden werden\\.", parse_mode="MarkdownV2")
            remove_profile(user_id)  # Bereinigung bei Fehler
    else:
        logger.info(f"[get_rules_ok] User {user_id} ist kein Mitglied ODER Reposting ist deaktiviert. Sende Einladungslink.")
        try:
            link: ChatInviteLink = await context.bot.create_chat_invite_link(
                chat_id=GROUP_ID,
                expire_date=datetime.utcnow() + timedelta(minutes=LINK_TTL_MINUTES),
                creates_join_request=True
            )
            await update.message.reply_text(
                f"✅ Super\\! Hier ist dein Einladungslink \\(gültig für {LINK_TTL_MINUTES} Minuten\\):\n{escape_markdown(link.invite_link, version=2)}",
                parse_mode='MarkdownV2'
            )
            # Hier NICHT remove_profile() aufrufen! Profil wird in handle_join_request benötigt.
        except Exception as e:
            logger.error(f"[get_rules_ok] Fehler beim Link-Erstellen für User {user_id}: {e}")
            await update.message.reply_text(f"⚠️ Fehler beim Erstellen des Links\\: {escape_markdown(str(e), version=2)}", parse_mode="MarkdownV2")
            remove_profile(user_id)  # Bereinigung bei Fehler

    user_data_temp.pop(user_id, None)
    return ConversationHandler.END


async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.chat_join_request.from_user
    config = load_bot_settings_config()
    GROUP_ID = int(config.get("main_chat_id", 0)) if config.get("main_chat_id") else 0
    TOPIC_ID_STR = config.get("topic_id")
    TOPIC_ID = int(TOPIC_ID_STR) if TOPIC_ID_STR and TOPIC_ID_STR.isdigit() else None
    repost_setting = config.get("repost_profile_for_existing_members", True)

    logger.debug(f"[handle_join_request] User: {user.id}, GROUP_ID: {GROUP_ID}, TOPIC_ID: {TOPIC_ID}, Repost Setting: {repost_setting}")

    if not GROUP_ID:
        logger.error("GROUP_ID ist nicht konfiguriert oder ungültig.")
        return

    is_already_member = False
    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_ID, user_id=user.id)
        is_already_member = member.status in ['member', 'administrator', 'creator']
        logger.debug(f"[handle_join_request] User {user.id} member status: {member.status}, is_already_member: {is_already_member}")
    except TelegramError as e:
        logger.debug(f"[handle_join_request] User {user.id} ist kein aktuelles Mitglied der Gruppe (Fehler: {e}).")
        is_already_member = False
    except Exception as e:
        logger.error(f"[handle_join_request] Fehler beim Abrufen des Chat-Mitgliedsstatus für User {user.id}: {e}", exc_info=True)

    try:
        await context.bot.approve_chat_join_request(chat_id=GROUP_ID, user_id=user.id)
        logger.info(f"[handle_join_request] Join request approved for user {user.id}")
    except Exception as e:
        logger.error(f"[handle_join_request] Genehmigung fehlgeschlagen für User {user.id}: {e}")
        return

    profile = load_profile(user.id)
    if not profile:
        logger.warning(f"[handle_join_request] Kein Profil für User {user.id} gefunden nach Genehmigung.")
        return

    should_post_profile = (not is_already_member) or (is_already_member and repost_setting)
    if should_post_profile:
        success = await _send_profile_to_group(user.id, profile, GROUP_ID, TOPIC_ID, context)
        if not success:
            logger.error(f"[handle_join_request] Profil konnte nicht in Gruppe gepostet werden für User {user.id}")

    remove_profile(user.id)


async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = load_bot_settings_config()
    GROUP_ID = int(config.get("main_chat_id", 0)) if config.get("main_chat_id") else 0
    TOPIC_ID_STR = config.get("topic_id")
    TOPIC_ID = int(TOPIC_ID_STR) if TOPIC_ID_STR and TOPIC_ID_STR.isdigit() else None

    if not update.message or not update.message.new_chat_members:
        return

    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            continue

        user_id = member.id
        profile = load_profile(user_id)
        if profile:
            await _send_profile_to_group(user_id, profile, GROUP_ID, TOPIC_ID, context)
            remove_profile(user_id)


async def handle_member_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.left_chat_member:
        return
    user = update.message.left_chat_member
    if user:
        remove_profile(user.id)
        logger.info(f"Benutzer {user.full_name} hat die Gruppe verlassen.")


# --- Bot Start --------------------------------------------------
if __name__ == "__main__":
    config = load_bot_settings_config()
    BOT_TOKEN = config.get("bot_token")
    is_enabled = config.get("is_enabled", False)

    if not BOT_TOKEN or not is_enabled:
        logger.info("Invite-Bot ist nicht aktiviert oder BOT_TOKEN fehlt.")
    else:
        app = ApplicationBuilder().token(BOT_TOKEN).build()

        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("letsgo", start_form)],
            states={
                ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
                ASK_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
                ASK_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_state)],
                # FIX: nicht nur PHOTO annehmen, sonst "hängt" der Bot wenn User Text/Dokument sendet
                ASK_PHOTO: [MessageHandler(filters.ALL & ~filters.COMMAND, get_photo)],
                ASK_HOBBIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hobbies)],
                ASK_INSTAGRAM: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_instagram)],
                ASK_OTHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_other)],
                ASK_SEXUALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_sexuality)],
                ASK_RULES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_rules_ok)],
            },
            fallbacks=[],
            per_message=False,
        )

        app.add_handler(CommandHandler("start", welcome))
        app.add_handler(CommandHandler("datenschutz", datenschutz))
        app.add_handler(conv_handler)
        app.add_handler(ChatJoinRequestHandler(handle_join_request))
        app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
        app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_member_left))

        developer_filter = filters.Regex(re.compile(r'^wer ist dein entwickler\??$', re.IGNORECASE))
        app.add_handler(MessageHandler(developer_filter & filters.TEXT & ~filters.COMMAND, reply_with_developer_info))

        praise_filter = filters.Regex(re.compile(r'^cooler bot!?$', re.IGNORECASE))
        app.add_handler(MessageHandler(praise_filter & filters.TEXT & ~filters.COMMAND, reply_with_developer_info))

        logger.info("🤖 Invite-Bot läuft …")
        app.run_polling()
