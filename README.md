# Telegram Bot Control Panel

Ein robustes Flask-basiertes Web-Panel zur zentralisierten Verwaltung von zwei spezialisierten Telegram-Bots: einem Einladungs-Bot für die Nutzerregistrierung und einem Outfit-Wettbewerb-Bot. Dieses System ermöglicht eine einfache Konfiguration, Überwachung und Steuerung beider Bots über eine intuitive Web-Oberfläche.

## Funktionen

*   **Zentrale Web-Oberfläche (Flask)**: Ein responsives Admin-Panel zur Verwaltung aller Bot-Einstellungen und zur Überwachung ihres Status.
*   **Einladungs-Bot (`invite_bot.py`)**:
    *   **Geführte Registrierung**: Nutzer füllen einen Steckbrief über eine Konversation im Bot aus.
    *   **Automatische Einladungen**: Generiert individuelle Einladungslinks zur Gruppe.
    *   **Profil-Posting**: Postet automatisch den Steckbrief des Nutzers beim Beitritt in die Gruppe.
    *   **Web-Konfiguration**: Aktivieren/Deaktivieren, Bot Token, Haupt-Chat ID der Gruppe, Gültigkeitsdauer der Einladungslinks über das Web-Panel konfigurierbar.
    *   **Status & Logs**: Echtzeit-Statusanzeige und Log-Ausgabe des Bots im Web-Panel.
*   **Outfit-Wettbewerb Bot (`outfit_bot.py`)**:
    *   **Tägliche Wettbewerbe**: Verwaltet das "Outfit des Tages" mit Fotoeinreichungen und Abstimmung.
    *   **Automatische Posts & Gewinner**: Sendet tägliche Aufforderungen und ermittelt Gewinner.
    *   **Web-Konfiguration**: Bot Token, Chat ID, Zeiten für Posts und Gewinner, Admin User IDs über das Web-Panel konfigurierbar.
    *   **Status & Logs**: Echtzeit-Statusanzeige und Log-Ausgabe des Bots im Web-Panel.
*   **Hintergrundprozesse**: Beide Bots laufen als unabhängige Hintergrundprozesse, gesteuert durch die Flask-Anwendung.
*   **Konfigurations-Persistenz**: Alle Bot-Einstellungen werden in JSON-Dateien gespeichert, um sie über Neustarts hinweg zu erhalten.
*   **Dunkles Design**: Eine angenehme, augenschonende Oberfläche für die Admin-Panels.

## Erste Schritte

Für eine detaillierte Installations- und Konfigurationsanleitung, einschließlich der Einrichtung von Telegram Bots und der benötigten Tokens/IDs, siehe die [INSTALL.md](INSTALL.md) Datei.

**Kurzanleitung:**

1.  Klonen Sie das Repository.
2.  Erstellen und aktivieren Sie eine Python-virtuelle Umgebung.
3.  Installieren Sie die Abhängigkeiten: `pip install -r requirements.txt`.
4.  Starten Sie die Flask-Anwendung: `./devserver.sh`.
5.  Konfigurieren Sie beide Bots über die Web-Oberfläche unter `http://localhost:8080/bot-settings` (für den Einladungs-Bot) und `http://localhost:8080/outfit-bot/dashboard` (für den Outfit-Bot).

## Projektstruktur

*   `app.py`: Die Haupt-Flask-Anwendung, die die Web-Oberflächen bereitstellt und die Bots als Hintergrundprozesse verwaltet.
*   `invite_bot.py`: Der Telegram-Bot für die Nutzerregistrierung, Profilerstellung und Einladungslinks.
*   `outfit_bot.py`: Der Telegram-Bot für den Outfit-Wettbewerb.
*   `src/`: Enthält die HTML-Vorlagen für die Web-Oberfläche (`index.html`, `bot_settings.html`, `outfit_bot_dashboard.html`).
*   `requirements.txt`: Listet alle Python-Abhängigkeiten auf.
*   `bot_settings_config.json`: Speichert die Konfiguration für den `invite_bot.py`.
*   `outfit_bot_config.json`: Speichert die Konfiguration für den `outfit_bot.py`.
*   `config.json`, `quizfragen.json`, `umfragen.json`, etc.: Weitere Konfigurations- und Datendateien für andere Funktionen.
*   `devserver.sh`: Skript zum Starten der Flask-Anwendung.

## Entwicklungsumgebung

Dieses Projekt ist für eine Nix-basierte Umgebung wie Firebase Studio konfiguriert, wobei Python 3 und eine virtuelle Umgebung (`.venv`) verwendet werden. Abhängigkeiten werden über `requirements.txt` verwaltet.

## Wichtiger Hinweis zur Bot-Ausführung

Um `telegram.error.Conflict` Fehler zu vermeiden, stellen Sie sicher, dass **nur eine Instanz jedes Bots** läuft. Die Flask-Anwendung (`app.py`) ist dafür ausgelegt, die Bots als Hintergrundprozesse zu starten und zu beenden. Starten Sie die Bot-Skripte (`invite_bot.py`, `outfit_bot.py`) niemals direkt aus dem Terminal, während `app.py` läuft.
