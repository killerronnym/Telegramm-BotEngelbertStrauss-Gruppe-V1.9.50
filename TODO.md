# 🚀 Neue Projekte

*   [ ] **Test-Suite erstellen:** Automatisierte Tests für die Kernfunktionen der Bots entwickeln, um zukünftige Änderungen abzusichern. (Langfristiges Ziel)

# 🎯 Offene Aufgaben

*   [ ] **Datenbank statt JSON:** Langfristig die Datenhaltung von JSON-Dateien auf eine robustere Lösung wie SQLite oder eine kleine Datenbank umstellen, um die Leistung und Zuverlässigkeit zu erhöhen.

---

## ✅ Fertiggestellte Aufgaben

*   [x] **Web-Oberfläche zur Telegram-Moderation:** Eine neue Seite im Dashboard erstellt, um Telegram-Gruppen zu moderieren.
    *   [x] Anzeige aller Gruppen und deren Topics.
    *   [x] Anzeige aller Nachrichten (inkl. Bilder und Usernamen) pro Topic.
    *   [x] Funktion zum Löschen von Nachrichten.
    *   [x] Option, beim Löschen eine Verwarnung an den User zu senden.
    *   [x] Option, Nachrichten kommentarlos zu löschen.
*   [x] **Telegram Media & Avatar Proxy:** Implementierung eines Proxys in Flask, um Avatare und Medien (Fotos) von Telegram sicher im Dashboard anzuzeigen.
*   [x] **Verwarnungssystem:** Integration eines Systems zur Nachverfolgung von Verwarnungen und automatischem Bann bei Erreichen des Limits (konfigurierbar).
*   [x] **Erweitertes Dashboard:** Dashboards für Quiz-Bot, Umfrage-Bot und Outfit-Bot mit Einstellungsverwaltung und Live-Logs integriert.
*   [x] **Minecraft Status Integration:** Live-Anzeige des Minecraft-Server-Status und Steuerung des Status-Bots über das Web-Interface.
*   [x] **Kritische Fehler-Ansicht:** Zentrale Ansicht im Dashboard für kritische Fehler (`critical_errors.log`), um Probleme schnell zu identifizieren.
*   [x] **Robuste Fehlerbehandlung in `track_activity`:** Sichergestellt, dass bei Fehlern im globalen Activity-Log (`activity_log.jsonl`) die Verarbeitung abbricht, um Inkonsistenzen zu vermeiden.
*   [x] **Asynchrone Dateizugriffe:** Die synchronen Dateizugriffe in `bots/id_finder_bot/id_finder_bot.py` in asynchrone Operationen umgewandelt.
*   [x] **Bot-Startprozess optimieren:** Startprozess robuster gemacht und Prozessabfrage im Dashboard optimiert.
*   [x] **API-Endpunkte prüfen:** Alle externen API-Abfragen (z.B. Minecraft-Server-Status) auf Robustheit und korrekte Fehlerbehandlung getestet.
*   [x] **Funktionalität aller Bots testen & fixen:** Jeden Bot einzeln auf seine Kernfunktionen geprüft, Fehler behoben und Robustheit erhöht.
    *   [x] **Invite Bot:** Conversation-Logik gefixt, Markdown-Escaping, Join-Request-Handler korrigiert.
    *   [x] **Outfit Bot:** Threading-Probleme behoben, Pfade absolut gesetzt, Duell-Logik stabilisiert.
    *   [x] **Quiz Bot:** Persistenz für `last_sent_date` eingebaut, API-Limits validiert.
    *   [x] **Umfrage Bot:** Persistenz für `last_sent_date` eingebaut, API-Limits validiert.
*   [x] **Web-Dashboard Stabilität:** Prozess-Abfrage optimiert, Session-Key ausgelagert.
*   [x] **Logging verbessern:** Zentrale Logging-Konfiguration und Rotation für alle Module.
*   [x] **Code-Refactoring:** Code auf Lesbarkeit und Wartbarkeit optimiert.
*   [x] **Dokumentation erweitern:** README.md und andere Dokumentationsdateien aktualisiert.
*   [x] **Optimierte Broadcast-Engine:** Umstellung auf `job_queue.run_once()` für effizienteres Senden.
*   [x] **Effizienteres Log-Handling:** Optimiertes Einlesen großer Log-Dateien.
*   [x] **Caching für Konfigurationsdateien:** Strategie zur Minimierung von Festplattenzugriffen implementiert.
