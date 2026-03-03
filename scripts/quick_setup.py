#!/usr/bin/env python3
"""
Quick Setup Script - Setzt das Bot Dashboard direkt auf, ohne den Web-Installer.
Führe aus mit: python scripts/quick_setup.py
"""
import os
import sys
import shutil

# Projekt-Root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

ENV_PATH = os.path.join(PROJECT_ROOT, '.env')
LOCK_PATH = os.path.join(PROJECT_ROOT, 'instance', 'installed.lock')
DB_PATH   = os.path.join(PROJECT_ROOT, 'instance', 'app.db')

print("\n" + "="*60)
print("  BOT ENGINE v2 - DIREKTES SETUP")
print("="*60)

# ── Schritt 1: Backup-Datei (optional) ──────────────────────────
print("\n[1/5] Datenbank-Backup wiederherstellen")
backup_input = input("Pfad zur Backup-Datei (Enter überspringen): ").strip().strip('"')

if backup_input and os.path.exists(backup_input):
    with open(backup_input, 'rb') as f:
        header = f.read(16)
    if header == b'SQLite format 3\x00':
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        if os.path.exists(DB_PATH):
            shutil.copy2(DB_PATH, DB_PATH + '.bak')
            print(f"  Altes Backup gesichert: {DB_PATH}.bak")
        shutil.copy2(backup_input, DB_PATH)
        size_kb = round(os.path.getsize(DB_PATH) / 1024, 1)
        print(f"  ✅ Backup wiederhergestellt: {os.path.basename(backup_input)} ({size_kb} KB)")
    else:
        print("  ⚠️  Keine gültige SQLite-Datei — übersprungen.")
elif backup_input:
    print(f"  ⚠️  Datei nicht gefunden: {backup_input} — übersprungen.")
else:
    print("  ↩  Übersprungen.")

# ── Schritt 2: Telegram Token ────────────────────────────────────
print("\n[2/5] Telegram Bot Token")
# Aktuellen Token aus .env lesen
current_token = ''
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith('TELEGRAM_BOT_TOKEN='):
                current_token = line.split('=', 1)[1].strip()
                break

if current_token:
    print(f"  Aktueller Token: {current_token[:20]}...{current_token[-10:]}")
    token_input = input("  Neuen Token eingeben (Enter = aktuellen behalten): ").strip()
    telegram_token = token_input if token_input else current_token
else:
    telegram_token = input("  Bot Token (von @BotFather): ").strip()

# ── Schritt 3: Gruppen-ID ────────────────────────────────────────
print("\n[3/5] Telegram Gruppen-ID")
current_group = ''
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            if line.startswith('GROUP_ID='):
                current_group = line.split('=', 1)[1].strip()
                break

if current_group:
    print(f"  Aktuelle Group ID: {current_group}")
    group_input = input("  Neue Group ID eingeben (Enter = aktuellen behalten): ").strip()
    group_id = group_input if group_input else current_group
else:
    group_id = input("  Gruppen-ID (z.B. -1001234567890): ").strip()

topic_id = input("  Topic-ID (Enter überspringen): ").strip()
owner_id = input("  Owner Telegram-ID (Enter überspringen): ").strip()

# ── Schritt 4: Admin-Account ─────────────────────────────────────
print("\n[4/5] Admin-Account")
admin_user = input("  Benutzername: ").strip()
admin_pass = input("  Passwort: ").strip()

# ── Schritt 5: Konfiguration speichern ──────────────────────────
print("\n[5/5] Konfiguration speichern...")

# .env schreiben
db_url = f"sqlite:///{DB_PATH}"
lines = []
if os.path.exists(ENV_PATH):
    with open(ENV_PATH) as f:
        lines = f.readlines()

prefixes = ["DATABASE_URL=", "TELEGRAM_BOT_TOKEN=", "OWNER_ID=", "GROUP_ID=", "TOPIC_ID="]
new_lines = [l for l in lines if not any(l.startswith(p) for p in prefixes)]
if new_lines and not new_lines[-1].endswith('\n'):
    new_lines.append('\n')

new_lines += [
    f"DATABASE_URL={db_url}\n",
    f"TELEGRAM_BOT_TOKEN={telegram_token}\n",
    f"OWNER_ID={owner_id}\n",
    f"GROUP_ID={group_id}\n",
    f"TOPIC_ID={topic_id}\n",
]

with open(ENV_PATH, 'w') as f:
    f.writelines(new_lines)
print("  ✅ .env aktualisiert")

# Datenbank & Admin-User anlegen
from dotenv import load_dotenv
load_dotenv(ENV_PATH, override=True)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(db_url)

# Import models
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'web_dashboard'))
from app.models import db as flask_db, User

flask_db.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

existing = session.query(User).filter_by(username=admin_user).first()
if existing:
    existing.set_password(admin_pass)
    existing.role = 'admin'
    print(f"  ✅ Admin-Passwort für '{admin_user}' aktualisiert")
else:
    admin = User(username=admin_user, role='admin')
    admin.set_password(admin_pass)
    session.add(admin)
    print(f"  ✅ Admin-Account '{admin_user}' erstellt")

session.commit()
session.close()

# Lock-Datei erstellen
os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
with open(LOCK_PATH, 'w') as f:
    f.write("Installed via quick_setup.py on Windows")
print("  ✅ Lock-Datei erstellt")

print("\n" + "="*60)
print("  SETUP ABGESCHLOSSEN!")
print("="*60)
print(f"\n  Bot Token:  {'SET (' + telegram_token[:15] + '...)' if telegram_token else 'NICHT GESETZT'}")
print(f"  Group ID:   {group_id or 'NICHT GESETZT'}")
print(f"  Admin:      {admin_user}")
print(f"  Datenbank:  {db_url}")
print("\n  Starte den Server mit: devserver.ps1")
print("  Dann im Browser: http://127.0.0.1:9002/auth/login\n")
