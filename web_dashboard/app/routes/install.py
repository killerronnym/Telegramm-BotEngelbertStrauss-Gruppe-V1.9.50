from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, current_app
from ..models import db, User
import os
import json
from sqlalchemy import text
from ..config import Config
from urllib.parse import quote_plus
import requests
import shutil
import traceback
import sys

bp = Blueprint('install', __name__, url_prefix='/install')

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
INSTALL_LOCK = os.path.join(PROJECT_ROOT, 'instance', 'installed.lock')
user_msgs_dir = os.path.join(PROJECT_ROOT, 'bots', 'data', 'user_messages')

def call_telegram(method, token, params=None, json=None, timeout=12):
    """Helper to call Telegram API with logging and error handling."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    print(f"[DEBUG] Calling Telegram: {method}")
    try:
        if json:
            res = requests.post(url, json=json, timeout=timeout)
        else:
            res = requests.get(url, params=params, timeout=timeout)
        
        print(f"[DEBUG] Status: {res.status_code}")
        try:
            return res.json()
        except Exception:
            print(f"[ERROR] Non-JSON response: {res.text[:200]}")
            return {"ok": False, "description": f"Server Error ({res.status_code})"}
            
    except requests.exceptions.Timeout:
        print("[ERROR] Telegram API Timeout")
        return {"ok": False, "description": "Verbindung zu Telegram fehlgeschlagen (Timeout)"}
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Telegram API Error: {str(e)}")
        return {"ok": False, "description": f"Verbindungsfehler: {str(e)}"}

def cleanup_personal_data():
    """Removes bot logs, persistence files, and user-specific data."""
    paths_to_delete = [
        os.path.join(PROJECT_ROOT, 'bots', 'main_bot.log'),
        os.path.join(PROJECT_ROOT, 'bots', 'persistence.pickle'),
        os.path.join(PROJECT_ROOT, 'bots', 'data', 'activity_log.jsonl'),
        os.path.join(PROJECT_ROOT, 'bots', 'data', 'profiles.json'),
        os.path.join(PROJECT_ROOT, 'bots', 'data', 'user_registry.json'),
    ]
    
    # import shutil removed (now at top level)
    for path in paths_to_delete:
        if os.path.exists(path):
            try:
                os.remove(path)
                print(f"Deleted: {path}")
            except Exception as e:
                print(f"Failed to delete {path}: {e}")
                
    if os.path.exists(user_msgs_dir):
        try:
            shutil.rmtree(user_msgs_dir)
            os.makedirs(user_msgs_dir, exist_ok=True)
            print(f"Cleared user_messages directory")
        except Exception as e:
            print(f"Failed to clear {user_msgs_dir}: {e}")

@bp.route('/')
def index():
    if os.path.exists(INSTALL_LOCK):
        return redirect(url_for('dashboard.index'))
    return render_template('install.html')

@bp.route('/check-db', methods=['POST'])
def check_db():
    data = request.json
    db_type = data.get('db_type')
    
    if db_type == 'sqlite':
        from shared_bot_utils import DB_PATH
        db_dir = os.path.dirname(DB_PATH)
        
        # Check if directory is writable
        if not os.access(db_dir, os.W_OK):
            return jsonify({"success": False, "error": f"Verzeichnis nicht beschreibbar: {db_dir}. Bitte prüfe die Dateiberechtigungen."})
        
        db_url = f"sqlite:///{DB_PATH}"
    else:
        host = data.get('host', 'localhost')
        port = data.get('port', '3306')
        user = data.get('user', '')
        password = data.get('password', '')
        dbname = data.get('dbname', 'bot_engine')
        
        user_enc = quote_plus(user)
        pass_enc = quote_plus(password)
        db_url = f"mysql+pymysql://{user_enc}:{pass_enc}@{host}:{port}/{dbname}?charset=utf8mb4"

    try:
        from sqlalchemy import create_engine
        # Short timeout for testing
        engine = create_engine(db_url, connect_args={'connect_timeout': 5} if db_type == 'mysql' else {})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return jsonify({"success": True, "db_url": db_url})
    except Exception as e:
        err_str = str(e)
        german_err = "Verbindung fehlgeschlagen."
        
        if "Access denied" in err_str:
            german_err = "Zugriff verweigert. Bitte prüfe Nutzername und Passwort."
        elif "Can't connect to MySQL server on" in err_str or "getaddrinfo failed" in err_str:
            german_err = "Server nicht erreichbar. Prüfe Host und Port (ggf. Firewall?)."
        elif "Unknown database" in err_str:
            german_err = f"Datenbank '{data.get('dbname')}' existiert nicht auf dem Server."
        elif "Timeout" in err_str:
            german_err = "Zeitüberschreitung bei der Verbindung (Timeout)."
        else:
            german_err = f"Fehler: {err_str}"
            
        return jsonify({"success": False, "error": german_err})

@bp.route('/setup', methods=['POST'])
def setup():
    if os.path.exists(INSTALL_LOCK):
        return jsonify({"success": False, "error": "Already installed"})

    data = request.json
    print("=" * 50)
    print("INSTALL SETUP CALLED!")
    print(f"  db_type: {data.get('db_type')}")
    print(f"  admin_user: {data.get('admin_user')}")
    print(f"  telegram_token: {'SET' if data.get('telegram_token') else 'EMPTY'}")
    
    # NEW: Cleanup personal data BEFORE setup if it's a fresh SQLite install
    if data.get('db_type') == 'sqlite':
        cleanup_personal_data()
        
    print(f"  main_group_id: {data.get('main_group_id')}")
    print(f"  admin_group_id: {data.get('admin_group_id')}")
    print(f"  admin_topic_id: {data.get('admin_topic_id')}")
    print("=" * 50)

    db_url = data.get('db_url')
    db_type = data.get('db_type')
    admin_user = data.get('admin_user')
    admin_pass = data.get('admin_pass')
    telegram_token = data.get('telegram_token', '')
    owner_id = data.get('owner_id', '')
    main_group_id = data.get('main_group_id', '')
    admin_group_id = data.get('admin_group_id', '')
    admin_topic_id = data.get('admin_topic_id', '')

    if db_type == 'sqlite':
        from shared_bot_utils import DB_PATH
        db_url = f"sqlite:///{DB_PATH}"
    elif not db_url or db_url == '':
        # Build MySQL URL if not provided directly
        host = data.get('host', 'localhost')
        port = data.get('port', '3306')
        user = quote_plus(data.get('user', ''))
        password = quote_plus(data.get('password', ''))
        dbname = data.get('dbname', 'bot_engine')
        db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}?charset=utf8mb4"

    try:
        # Update .env file
        env_path = os.path.join(PROJECT_ROOT, '.env')
        lines = []
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
        
        # Remove existing entries
        prefixes_to_remove = ["DATABASE_URL=", "TELEGRAM_BOT_TOKEN=", "OWNER_ID=", "GROUP_ID=", "TOPIC_ID=", "MAIN_GROUP_ID=", "ADMIN_GROUP_ID=", "ADMIN_LOG_TOPIC_ID="]
        new_lines = [l for l in lines if not any(l.startswith(p) for p in prefixes_to_remove)]

        if new_lines and not new_lines[-1].endswith("\n"):
             new_lines.append("\n")
        
        new_lines.append(f"DATABASE_URL={db_url}\n")
        if telegram_token:
            new_lines.append(f"TELEGRAM_BOT_TOKEN={telegram_token}\n")
        if main_group_id:
            new_lines.append(f"GROUP_ID={main_group_id}\n")
            new_lines.append(f"MAIN_GROUP_ID={main_group_id}\n")
        if admin_group_id:
            new_lines.append(f"ADMIN_GROUP_ID={admin_group_id}\n")
        if admin_topic_id:
            new_lines.append(f"ADMIN_LOG_TOPIC_ID={admin_topic_id}\n")
        
        with open(env_path, 'w') as f:
            f.writelines(new_lines)
        
        # Initialize tables using a direct SQLAlchemy engine to avoid Flask-SQLAlchemy using the old cached .env engine
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        engine = create_engine(db_url)
        db.metadata.create_all(engine)
        
        Session = sessionmaker(bind=engine)
        session = Session()
        
        if not session.query(User).filter_by(username=admin_user).first():
            new_admin = User(username=admin_user, role='admin')
            new_admin.set_password(admin_pass)
            session.add(new_admin)
            session.commit()

        # Write token and group into BotSettings for the id_finder bot
        # This is what the bot actually reads at runtime!
        from ..models import BotSettings
        import json as _json
        id_finder_row = session.query(BotSettings).filter_by(bot_name='id_finder').first()
        if id_finder_row:
            try:
                cfg = _json.loads(id_finder_row.config_json) if id_finder_row.config_json else {}
            except Exception:
                cfg = {}
        else:
            cfg = {}
            id_finder_row = BotSettings(bot_name='id_finder', config_json='{}')
            session.add(id_finder_row)

        if telegram_token:
            cfg['bot_token'] = telegram_token
        
        # Main Group
        try:
            cfg['main_group_id'] = int(main_group_id) if str(main_group_id).lstrip('-').isdigit() else 0
        except:
            cfg['main_group_id'] = 0
            
        # Admin Group
        try:
            cfg['admin_group_id'] = int(admin_group_id) if str(admin_group_id).lstrip('-').isdigit() else 0
        except:
            cfg['admin_group_id'] = 0
            
        # Admin Log Topic
        try:
            cfg['admin_log_topic_id'] = int(admin_topic_id) if str(admin_topic_id).lstrip('-').isdigit() else 0
        except:
            cfg['admin_log_topic_id'] = 0
        id_finder_row.config_json = json.dumps(cfg)
        session.commit()
        session.close()

        # Create lock file
        os.makedirs(os.path.dirname(INSTALL_LOCK), exist_ok=True)
        with open(INSTALL_LOCK, 'w') as f:
            f.write("Installed on Windows")

        # Reload env vars into the running process immediately
        os.environ['TELEGRAM_BOT_TOKEN'] = telegram_token
        os.environ['GROUP_ID'] = str(main_group_id)
        os.environ['MAIN_GROUP_ID'] = str(main_group_id)
        os.environ['ADMIN_GROUP_ID'] = str(admin_group_id)
        os.environ['ADMIN_LOG_TOPIC_ID'] = str(admin_topic_id)
        os.environ['DATABASE_URL'] = db_url

        print(f"Setup Complete! Token={'SET' if telegram_token else 'EMPTY'}, MainGroup={main_group_id}, Admin={admin_user}")
        return jsonify({"success": True})
    except Exception as e:
        import traceback
        print(f"SETUP ERROR: {e}")
        print(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)})

@bp.route('/test-token', methods=['POST'])
def test_token():
    token = request.json.get('token')
    if not token:
        return jsonify({"success": False, "error": "Kein Token angegeben"})
    
    # Use robust helper
    data = call_telegram("getMe", token)
    if data.get("ok"):
        return jsonify({"success": True, "bot_name": data["result"].get("first_name")})
    return jsonify({"success": False, "error": data.get("description", "Ungültiger Token")})

@bp.route('/get-group-id', methods=['POST'])
def get_group_id():
    token = request.json.get('token')
    if not token:
        return jsonify({"success": False, "error": "Kein Token vorhanden"})
    
    try:
        # Use robust helper
        data = call_telegram("getUpdates", token, params={"limit": 100})
        if not data.get("ok"):
            return jsonify({"success": False, "error": data.get("description", "Fehler beim Abrufen")})
            
        updates = data.get("result", [])
        if not updates:
            return jsonify({"success": False, "error": "Keine neuen Nachrichten gefunden. Bitte sende /id in die Gruppe!"})
        
        # Find latest /id command
        found_update = None
        for u in reversed(updates):
            msg = u.get("message", {})
            text_val = msg.get("text", "")
            if text_val.startswith("/id"):
                found_update = u
                break
        
        if not found_update:
            return jsonify({"success": False, "error": "Befehl /id nicht gefunden. Bitte sende ihn erneut."})
        
        chat = found_update["message"]["chat"]
        chat_id = chat["id"]
        chat_name = chat.get("title", chat.get("first_name", "Unbekannt"))
        
        # Clear processed updates
        try:
            next_offset = found_update["update_id"] + 1
            call_telegram("getUpdates", token, params={"offset": next_offset, "limit": 1}, timeout=5)
        except:
            pass

        # Send confirmation message
        try:
            confirm_text = f"✅ *ID erkannt!*\n\nHier ist die Gruppen-ID: `{chat_id}`\nBitte bestätige diese jetzt in deinem Browser."
            call_telegram("sendMessage", token, json={"chat_id": chat_id, "text": confirm_text, "parse_mode": "Markdown"}, timeout=5)
        except:
            pass

        return jsonify({
            "success": True,
            "chat_id": chat_id,
            "chat_name": chat_name,
            "chat_type": chat["type"]
        })
    except Exception as e:
        import traceback
        print(f"[CRITICAL ERROR] get_group_id failed: {str(e)}")
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Interner Serverfehler: {str(e)}"})
@bp.route('/send-test-message', methods=['POST'])
def send_test_message():
    token = request.json.get('token')
    chat_id = request.json.get('chat_id')
    
    if not token or not chat_id:
        return jsonify({"success": False, "error": "Token und Chat ID erforderlich"})
        
    text = "🔔 *Test-Nachricht*\n\nDie Verbindung zum Bot-Dashboard wurde erfolgreich hergestellt! 🎉"
    data = call_telegram("sendMessage", token, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    })
    
    if data.get("ok"):
        return jsonify({"success": True})
    return jsonify({"success": False, "error": data.get("description", "Fehler beim Senden")})

@bp.route('/validate-backup', methods=['POST'])
def validate_backup():
    if 'backup_file' not in request.files:
        return jsonify({"success": False, "error": "Keine Datei hochgeladen"})
        
    file = request.files['backup_file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Keine Datei ausgewählt"})

    temp_path = os.path.join(PROJECT_ROOT, 'instance', 'temp_validate.db')
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    
    try:
        file.save(temp_path)
        
        # Check SQLite header
        with open(temp_path, 'rb') as f:
            header = f.read(16)
            if header != b'SQLite format 3\x00':
                os.remove(temp_path)
                return jsonify({"success": False, "error": "Die Datei ist keine gültige SQLite-Datenbank."})

        from sqlalchemy import create_engine, inspect
        engine = create_engine(f"sqlite:///{temp_path}")
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        # Required tables for a valid "Bot Engine v2" backup
        required = ['User', 'BotSettings', 'Profiles']
        missing = [t for t in required if t not in tables]
        
        if missing:
            os.remove(temp_path)
            return jsonify({
                "success": False, 
                "error": f"Ungültiges Backup. Folgende Tabellen fehlen: {', '.join(missing)}. "
                         "Dies scheint kein Backup der Bot Engine v2 zu sein."
            })

        # Gather stats
        with engine.connect() as conn:
            user_count = conn.execute(text("SELECT COUNT(*) FROM User")).scalar()
            bot_count = conn.execute(text("SELECT COUNT(*) FROM BotSettings")).scalar()
            profile_count = conn.execute(text("SELECT COUNT(*) FROM Profiles")).scalar()
            
        os.remove(temp_path)
        
        return jsonify({
            "success": True,
            "filename": file.filename,
            "stats": {
                "users": user_count,
                "bots": bot_count,
                "profiles": profile_count
            }
        })
        
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"success": False, "error": f"Fehler bei der Validierung: {str(e)}"})

@bp.route('/restore', methods=['POST'])
def restore():
    if os.path.exists(INSTALL_LOCK):
        return jsonify({"success": False, "error": "Bereits installiert"})

    if 'backup_file' not in request.files:
        return jsonify({"success": False, "error": "Keine Datei hochgeladen"}), 400
        
    file = request.files['backup_file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Keine Datei ausgewählt"}), 400

    # Read all extra config from form (sent by JS)
    telegram_token = request.form.get('telegram_token', '')
    main_group_id = request.form.get('main_group_id', '')
    admin_group_id = request.form.get('admin_group_id', '')
    admin_topic_id = request.form.get('admin_topic_id', '')
    admin_user = request.form.get('admin_user', '')
    admin_pass = request.form.get('admin_pass', '')
        
    from shared_bot_utils import DB_PATH
    
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        # Save uploaded backup directly
        file.save(DB_PATH)
        
        # Validate SQLite header
        with open(DB_PATH, 'rb') as f:
            header = f.read(16)
            if header != b'SQLite format 3\x00':
                os.remove(DB_PATH)
                return jsonify({"success": False, "error": "Ungültige SQLite Datei"}), 400

        # Update .env with ALL settings
        env_path = os.path.join(PROJECT_ROOT, '.env')
        db_url = f"sqlite:///{DB_PATH}"
        lines = []
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                lines = f.readlines()
        
        # Remove existing entries
        prefixes_to_remove = ["DATABASE_URL=", "TELEGRAM_BOT_TOKEN=", "OWNER_ID=", "GROUP_ID=", "TOPIC_ID=", "MAIN_GROUP_ID=", "ADMIN_GROUP_ID=", "ADMIN_LOG_TOPIC_ID="]
        new_lines = [l for l in lines if not any(l.startswith(p) for p in prefixes_to_remove)]
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"DATABASE_URL={db_url}\n")
        if telegram_token:
            new_lines.append(f"TELEGRAM_BOT_TOKEN={telegram_token}\n")
        if main_group_id:
            new_lines.append(f"GROUP_ID={main_group_id}\n")
            new_lines.append(f"MAIN_GROUP_ID={main_group_id}\n")
        if admin_group_id:
            new_lines.append(f"ADMIN_GROUP_ID={admin_group_id}\n")
        if admin_topic_id:
            new_lines.append(f"ADMIN_LOG_TOPIC_ID={admin_topic_id}\n")
        
        with open(env_path, 'w') as f:
            f.writelines(new_lines)

        # Create admin user if credentials were provided
        if admin_user and admin_pass:
            try:
                from sqlalchemy import create_engine
                from sqlalchemy.orm import sessionmaker
                engine = create_engine(db_url)
                db.metadata.create_all(engine)
                Session = sessionmaker(bind=engine)
                session = Session()
                
                # 1. Create User
                existing = session.query(User).filter_by(username=admin_user).first()
                if not existing:
                    admin = User(username=admin_user, role='admin')
                    admin.set_password(admin_pass)
                    session.add(admin)
                    session.commit()
                
                # 2. Sync BotSettings in the restored database
                try:
                    # id_finder is used for global group/token settings
                    from sqlalchemy import Table, MetaData
                    metadata = MetaData()
                    bot_settings = Table('BotSettings', metadata, autoload_with=engine)
                    
                    # Check if bot exists
                    q_bot = session.execute(text("SELECT id, config_json FROM BotSettings WHERE bot_name = 'id_finder'")).fetchone()
                    if q_bot:
                        bot_id, config_str = q_bot
                        cfg = json.loads(config_str) if config_str else {}
                        if telegram_token: cfg['telegram_token'] = telegram_token
                        if main_group_id: cfg['main_group_id'] = int(main_group_id) if str(main_group_id).lstrip('-').isdigit() else 0
                        if admin_group_id: cfg['admin_group_id'] = int(admin_group_id) if str(admin_group_id).lstrip('-').isdigit() else 0
                        if admin_topic_id: cfg['admin_log_topic_id'] = int(admin_topic_id) if str(admin_topic_id).lstrip('-').isdigit() else 0
                        
                        session.execute(
                            text("UPDATE BotSettings SET config_json = :cfg WHERE id = :id"),
                            {"cfg": json.dumps(cfg), "id": bot_id}
                        )
                        session.commit()
                        print(f"BotSettings synced for 'id_finder' in restored DB.")
                except Exception as ex:
                    print(f"Warnung: BotSettings konnten nicht synchronisiert werden: {ex}")
                    session.rollback()

                session.close()
            except Exception as e:
                print(f"Warnung: Admin-User/Settings konnten nicht erstellt werden: {e}")

        # Create lock file
        os.makedirs(os.path.dirname(INSTALL_LOCK), exist_ok=True)
        with open(INSTALL_LOCK, 'w') as f:
            f.write(f"Restored from backup on Windows")

        # File info for UI
        size_mb = round(os.path.getsize(DB_PATH) / (1024 * 1024), 2)

        # Restart server (devserver.ps1 will auto-restart)
        import threading
        import time
        def restart_server():
            time.sleep(2)
            print("Restore Complete! Restarting server process...")
            os._exit(0)
            
        threading.Thread(target=restart_server, daemon=True).start()

        return jsonify({"success": True, "filename": file.filename, "size": f"{size_mb} MB"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
