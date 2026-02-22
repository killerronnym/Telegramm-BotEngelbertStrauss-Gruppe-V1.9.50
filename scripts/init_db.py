import sys
import os

# Füge das Projektverzeichnis zum Pfad hinzu
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_dashboard.app import create_app, db
from web_dashboard.app.models import User, BotSettings

app = create_app()

with app.app_context():
    print("Erstelle Datenbank-Tabellen...")
    db.create_all()

    # Erstelle Standard-Admin, falls nicht vorhanden
    if not User.query.filter_by(username='admin').first():
        print("Erstelle initialen Admin-Account 'admin' / 'admin'...")
        admin = User(username='admin', role='admin')
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()
        print("Admin-Account erstellt. Bitte Passwort ändern!")
    else:
        print("Admin-Account existiert bereits.")

    # Initiale Bot-Einstellungen (Beispiel)
    bots = ['quiz_bot', 'umfrage_bot', 'outfit_bot', 'invite_bot', 'id_finder_bot']
    for bot_name in bots:
        if not BotSettings.query.filter_by(bot_name=bot_name).first():
            print(f"Initialisiere Einstellungen für {bot_name}...")
            bot = BotSettings(bot_name=bot_name, config_json='{}', is_active=False)
            db.session.add(bot)
    
    db.session.commit()
    print("Datenbank-Initialisierung abgeschlossen.")
