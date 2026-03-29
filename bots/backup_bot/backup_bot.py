import os
import shutil
import logging
import json
from datetime import datetime, time
from telegram.ext import ContextTypes, Application
from shared_bot_utils import DB_PATH, PROJECT_ROOT, get_bot_config, get_shared_flask_app

logger = logging.getLogger(__name__)

# Backup directories
LOCAL_BACKUP_DIR = os.path.join(PROJECT_ROOT, "instance", "backups")

async def perform_backup(context: ContextTypes.DEFAULT_TYPE = None):
    """Main backup logic."""
    if context:
        await notify_admin(context, "🔄 <b>Automatisches Backup gestartet...</b>\nDie Datenbank wird gesichert.")
    
    logger.info("Starting automated database backup...")
    
    config = get_bot_config('backup_bot')
    if not config or not config.get('enabled'):
        logger.info("Backup is disabled in settings.")
        return

    nas_path = config.get('nas_path')
    local_retention = config.get('local_retention', 7)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"app_backup_{timestamp}.db"
    
    # 1. Local Backup for Redundancy
    try:
        os.makedirs(LOCAL_BACKUP_DIR, exist_ok=True)
        local_path = os.path.join(LOCAL_BACKUP_DIR, backup_filename)
        shutil.copy2(DB_PATH, local_path)
        logger.info(f"Local backup created: {local_path}")
        
        # Cleanup old local backups
        if local_retention > 0:
            all_backups = sorted([f for f in os.listdir(LOCAL_BACKUP_DIR) if f.startswith("app_backup_")])
            if len(all_backups) > local_retention:
                for old_f in all_backups[:-local_retention]:
                    os.remove(os.path.join(LOCAL_BACKUP_DIR, old_f))
                    logger.info(f"Deleted old local backup: {old_f}")
    except Exception as e:
        logger.error(f"Error during local backup: {e}")
        if context:
            await notify_admin(context, f"❌ Fehler beim lokalen Datenbank-Backup: {e}")

    # 2. NAS Backup
    if nas_path:
        try:
            # Check if NAS path exists (might be a network share)
            if not os.path.exists(nas_path):
                # Try to create it if it's a local folder, otherwise it might fail if it's an unmounted share
                try:
                    os.makedirs(nas_path, exist_ok=True)
                except:
                    pass
            
            if os.path.exists(nas_path):
                nas_file_path = os.path.join(nas_path, backup_filename)
                shutil.copy2(DB_PATH, nas_file_path)
                logger.info(f"NAS backup created: {nas_file_path}")
                if context:
                    await notify_admin(context, f"✅ Automatisches Backup erfolgreich an NAS übertragen: `{backup_filename}`")
            else:
                logger.error(f"NAS path does not exist or is not accessible: {nas_path}")
                if context:
                    await notify_admin(context, f"⚠️ NAS-Zuspielpfad nicht erreichbar: `{nas_path}`. Backup nur lokal gesichert.")
        except Exception as e:
            logger.error(f"Error during NAS backup: {e}")
            if context:
                await notify_admin(context, f"❌ Fehler beim NAS-Backup: {e}")
    else:
        logger.warning("No NAS path configured.")
        if context:
            await notify_admin(context, "ℹ️ Automatisches Backup abgeschlossen (nur lokal, kein NAS-Pfad konfiguriert).")

async def notify_admin(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Sends a notification to the admin group or owner."""
    try:
        # Get admin chat from id_finder config
        id_config = get_bot_config('id_finder')
        admin_chat_id = id_config.get('admin_group_id')
        topic_id = id_config.get('admin_log_topic_id')
        
        if admin_chat_id:
            kwargs = {"chat_id": admin_chat_id, "text": f"💾 <b>BACKUP-SYSTEM</b>\n\n{message}", "parse_mode": "HTML"}
            if topic_id:
                kwargs["message_thread_id"] = topic_id
            await context.bot.send_message(**kwargs)
    except Exception as e:
        logger.error(f"Could not notify admin about backup: {e}")

def setup_jobs(job_queue):
    """Registers the daily backup job."""
    config = get_bot_config('backup_bot')
    if not config:
        return

    backup_time_str = config.get('backup_time', '06:55')
    try:
        h, m = map(int, backup_time_str.split(':'))
        backup_time = time(hour=h, minute=m)
    except:
        backup_time = time(hour=6, minute=55)

    # Register the job
    job_queue.run_daily(perform_backup, time=backup_time, name="daily_database_backup")
    logger.info(f"Daily backup job scheduled for {backup_time}")

def get_handlers():
    """No specific message handlers for backup bot yet."""
    return []
