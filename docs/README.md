# Telegramm-Bot-Ökosystem: NexusMod & Co.

Willkommen zu deinem persönlichen Telegramm-Bot-Control-Panel! Dieses Projekt bietet eine zentrale Verwaltungsoberfläche für mehrere spezialisierte Telegram-Bots, darunter der leistungsstarke **NexusMod Bot** (ehemals ID-Finder Bot), der **Minecraft Status Bot**, ein **Einladungs-Bot** und ein **Outfit-Wettbewerb-Bot**.

## ✨ Neuheiten & Highlights (Aktuelles Update)

In den letzten Updates wurden signifikante Verbesserungen an der Stabilität, Sicherheit und Benutzererfahrung vorgenommen:

*   **🔐 Sicheres Login-System:**
    *   **Benutzer-Authentifizierung:** Zugriff auf das Dashboard ist nur noch mit gültigen Zugangsdaten möglich.
    *   **Passwort-Hashing:** Passwörter werden sicher mit modernsten Algorithmen (PBKDF2/scrypt) verschlüsselt gespeichert.
    *   **Session-Management:** Sichere Sitzungsverwaltung verhindert unbefugten Zugriff.
    *   **Dark Mode Login:** Ein augenfreundliches, komplett dunkles Login-Interface.
*   **👥 Erweiterte Benutzerverwaltung:**
    *   **Rollenbasiert:** Unterscheidung zwischen **Admins** (voller Zugriff) und **Usern** (eingeschränkter Zugriff).
    *   **Zentrale Steuerung:** Direkt auf dem Dashboard können neue Benutzer angelegt, bearbeitet oder gelöscht werden.
    *   **Profil-Bearbeitung:** Benutzernamen, Passwörter und Rollen können jederzeit über ein intuitives Modal-Fenster geändert werden.
*   **🎨 Modernisiertes Dashboard-Design:**
    *   **Kachel-Interface:** Alle Funktionen sind über übersichtliche Kacheln erreichbar.
    *   **Navbar-Frei:** Die obere Navigationsleiste wurde entfernt, um mehr Platz für die Bot-Steuerung zu schaffen.
    *   **Status-Infos:** Der aktuell angemeldete Benutzer und seine Rolle werden dezent auf der Startseite angezeigt.
*   **🛡️ Minecraft Status Pro:** 
    *   **Anti-Duplikat-System:** Ein globaler `asyncio.Lock` verhindert doppelt gesendete Nachrichten bei Telegram-Timeouts.
    *   **Intelligente Rotation:** Status-Nachrichten werden alle 23 Stunden automatisch gelöscht und neu erstellt, um die 48h-Editiergrenze von Telegram sicher zu umgehen.
    *   **Cleanup-First:** Wenn eine Nachricht nicht mehr editiert werden kann, wird sie konsequent gelöscht, bevor eine neue erstellt wird. Nur eine Nachricht bleibt im Chat!
    *   **Robustes Logging:** Detailliertes Fehler-Logging inkl. Exception-Klassen für maximale Transparenz.
*   **📊 Analytics Dashboard:**
    *   **Recently Active Users:** Eine neue Tabelle im Dashboard zeigt die zuletzt aktiven Nutzer mit Zeitstempel und Avatar an.
    *   **Echtzeit-KPIs:** Verbesserte Berechnung von Nachrichtenvolumen, aktiven Nutzern und Top-Contributoren.
    *   **Daten-Registry:** Automatisierte Erfassung von Nutzern beim Beitritt oder Schreiben, um vollständige Statistiken zu gewährleisten.

## ✅ Vorgenommene Verbesserungen

*   **Robuste Fehlerbehandlung in `track_activity`:** Sichergestellt, dass bei Fehlern im globalen Activity-Log (`activity_log.jsonl`) die Verarbeitung abbricht, um Inkonsistenzen zu vermeiden, und dass Fehler beim User-Registry-Update nicht das gesamte Logging blockieren.
*   **Asynchrone Dateizugriffe:** Die synchronen Dateizugriffe (`load_json`, `save_json`, `_append_jsonl`) in `bots/id_finder_bot/id_finder_bot.py` in asynchrone Operationen umgewandelt (`run_in_executor`), um das Blockieren des Bots zu verhindern.
*   **Bot-Startprozess optimieren:** Überprüfen, ob alle Bots korrekt und ohne Verzögerungen starten. (Startprozess robuster gemacht und Prozessabfrage im Dashboard optimiert)
*   **API-Endpunkte prüfen:** Alle externen API-Abfragen (z.B. Minecraft-Server-Status) auf Robustheit und korrekte Fehlerbehandlung testen. (`minecraft_bridge.py` gehärtet und `mcstatus` als Dependency hinzugefügt)
*   **Funktionalität aller Bots testen & fixen:** Jeden Bot einzeln auf seine Kernfunktionen geprüft, Fehler behoben und Robustheit erhöht.
    *   **Invite Bot:** Conversation-Logik gefixt, Markdown-Escaping, Join-Request-Handler korrigiert.
    *   **Outfit Bot:** Threading-Probleme behoben, Pfade absolut gesetzt, Duell-Logik stabilisiert.
    *   **Quiz Bot:** Persistenz für `last_sent_date` eingebaut, API-Limits validiert.
    *   **Umfrage Bot:** Persistenz für `last_sent_date` eingebaut, API-Limits validiert.
*   **Web-Dashboard Stabilität:** Prüfen, ob das Dashboard auch bei vielen Anfragen stabil läuft und keine Sessions verliert. (Prozess-Abfrage optimiert, Session-Key ausgelagert)
*   **Logging verbessern (Web-Dashboard):** Detailliertere Log-Ausgaben implementiert, um Fehler schneller identifizieren zu können, inklusive zentraler Logging-Konfiguration.
*   **Spezifischere Fehlerbehandlung (Web-Dashboard):** Allgemeine `try...except`-Blöcke durch spezifische Fehlerbehandlung ersetzt und detaillierte Fehlermeldungen geloggt.
*   **Effizienteres Log-Handling (Web-Dashboard):** Das Einlesen von Log-Dateien optimiert, um den Speicherverbrauch bei großen Dateien zu reduzieren (z.B. durch zeilenweises Lesen oder Buffering).
*   **Code-Duplizierung reduzieren (Web-Dashboard):** Wiederholte Code-Blöcke in den Flask-Routen identifiziert und in wiederverwendbare Funktionen ausgelagert.
*   **Caching für Konfigurationsdateien (Web-Dashboard):** Eine Caching-Strategie für häufig gelesene JSON-Dateien implementiert, um die Anzahl der Festplattenzugriffe zu minimieren und die Performance zu verbessern.
*   **Optimierte Broadcast-Engine (ID Finder Bot):** Die Broadcast-Engine so umgebaut, dass sie nicht alle 10 Sekunden alle Nachrichten prüft, sondern gezielt den nächsten Sendezeitpunkt mit `job_queue.run_once()` ansteuert.
*   **Datenredundanz geprüft (ID Finder Bot):** Überprüft, ob die in `activity_log.jsonl` und der `user_messages`-History gespeicherten Daten zusammengefasst oder besser strukturiert werden können. (Anmerkung zur aktuellen Strategie hinzugefügt).
*   **Alte Skripte entfernt:** Der `archive`-Ordner mit veralteten Skripten wurde gelöscht.

## ⛏️ Minecraft Status Bot Features

*   **Live-Monitoring:** Überwacht Java-Minecraft-Server in Echtzeit (Spieleranzahl, MOTD, Version, Latenz).
*   **Vollautomatisches Dashboard:** Verwaltung aller IP-Daten, Ports und Topic-IDs direkt über das Web-UI.
*   **Auto-Cleanup:** Der `/player` Befehl löscht seine eigene Antwort automatisch nach X Sekunden (einstellbar).
*   **Präzise Anzeige:** Nutzt spezialisierte IP-Felder für interne Abfragen vs. öffentliche Anzeige im Chat.

## 🛡️ NexusMod Bot (Moderation & ID-Finder)

Der NexusMod Bot bleibt dein zentrales Werkzeug für die Gruppenmoderation:

*   **Moderations-Suite:** `/warn`, `/mute`, `/kick`, `/ban` mit flexiblen Zeitangaben (m/h/d).
*   **Chat-Tools:** `/del`, `/purge` (Massenlöschung), `/pin`, `/unpin`.
*   **Automatisierung:** `/lock` (Sperrung von Links, Medien oder Stickern), Anti-Flood-Schutz und Wortfilter.
*   **Identifikation:** Schnelle Abfrage von IDs mit `/id`, `/chatid`, `/userid` oder `/topicid`.

## 🌐 Zentrales Web-Dashboard

Das Dashboard (Standard-Port 9002) bietet die volle Kontrolle:

1.  **Start/Stop:** Alle Bots können einzeln gestartet und gestoppt werden.
2.  **Live-Logs:** Einblick in die Bot-Aktivitäten direkt im Browser.
3.  **Konfiguration:** Änderungen an Token, IDs und Timern werden sofort übernommen.
4.  **Benutzerverwaltung:** Nur für Admins zugänglich, um den Zugriff auf das System zu regeln.

---
*Entwickelt für maximale Kontrolle und Transparenz in deiner Telegram-Community.*
