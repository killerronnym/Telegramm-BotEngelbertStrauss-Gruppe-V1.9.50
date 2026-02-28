#!/bin/bash
# Updated: 2026-02-26 21:22

set -e

echo "--- Starting Bot Engine v2 Entrypoint ---"
export BOT_PROCESS=1

# Navigieren zum App-Verzeichnis
cd /app

# Prüfen auf neue Abhängigkeiten
if [ -f "requirements.txt" ]; then
    echo "Checking for dependency updates..."
    pip install --no-cache-dir -r requirements.txt
fi

# Datenbank-Migrationen oder andere Vorbereitungen könnten hier stehen
# python manage.py db upgrade

echo "Starting Gunicorn Flask server and Master-Bot..."
# Wir stellen sicher, dass die Datenbank (falls konfiguriert) bereit ist.
# Wenn es fehlschlägt, ist das okay, wir wollen ins Dashboard zum Setup Wizard!
python3 -c "
try:
    from web_dashboard.app import create_app, db
    app = create_app()
    with app.app_context():
        db.create_all()
    print('Database initialized.')
except Exception as e:
    print('Initial DB query failed (Missing config?). Continuing to Web Setup Wizard...')
" || echo "Initial DB setup deferred."

# Master-Bot im Hintergrund starten
echo "Launching Master-Bot in background..."
# Der Bot könnte sofort abstürzen, wenn keine DB da ist, das ist einkalkuliert
python bots/main_bot.py &
BOT_PID=$!
mkdir -p logs
echo $BOT_PID > logs/main_bot.pid

# Dashboard im Vordergrund (bindet an Port 9003)
echo "Launching Gunicorn on port 9003..."
gunicorn --bind 0.0.0.0:9003 --workers 2 --timeout 120 --access-logfile - --error-logfile - "web_dashboard.app:create_app()" &
WEB_PID=$!

# Trap: Wenn der Container gestoppt wird, beenden wir beide Prozesse sauber
cleanup() {
    echo "Stopping processes..."
    kill $BOT_PID $WEB_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# WICHTIG: Wir warten NUR auf Gunicorn ($WEB_PID).
# Falls der Bot stirbt (z.B. wegen fehlendem Token), bleibt der Webserver am Leben,
# damit der User im Installer / Dashboard alles konfigurieren kann.
echo "Monitoring Gunicorn (PID: $WEB_PID)..."
wait $WEB_PID

# Falls Gunicorn stoppt, reißen wir den Bot mit in den Abgrund und beenden alles.
# Dies wird z.B. vom Installer nach erfolgreichem Setup getriggert, um den Container neu zu starten.
kill $BOT_PID 2>/dev/null || true
exit 0
