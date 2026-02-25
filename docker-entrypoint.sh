#!/bin/bash
set -e

echo "--- Starting Bot Engine v2 Entrypoint ---"

# Navigieren zum App-Verzeichnis
cd /app

# Prüfen auf neue Abhängigkeiten
if [ -f "requirements.txt" ]; then
    echo "Checking for dependency updates..."
    pip install --no-cache-dir -r requirements.txt
fi

# Datenbank-Migrationen oder andere Vorbereitungen könnten hier stehen
# python manage.py db upgrade

# Wir stellen sicher, dass Log-Ordner existieren
mkdir -p bots logs instance

echo "Starting Gunicorn Flask server..."
# Gunicorn übernimmt das Dashboard
# Wir starten den Master-Bot NICHT direkt hier, damit er über das Dashboard 
# (wie gewohnt) oder via Docker-Compose gesteuert werden kann.
# Aber wir stellen sicher, dass die Datenbank bereit ist.
python -c "from web_dashboard.app import create_app, db; app=create_app(); with app.app_context(): db.create_all()"

exec gunicorn --bind 0.0.0.0:9002 --workers 2 --timeout 120 "web_dashboard.app:create_app()"
