# Telegramm-Bot-Ökosystem: NexusMod & Co.

Willkommen zu deinem persönlichen Telegramm-Bot-Control-Panel! Dieses Projekt bietet eine zentrale Verwaltungsoberfläche für mehrere spezialisierte Telegram-Bots, darunter der leistungsstarke **NexusMod Bot** (ehemals ID-Finder Bot), der **Minecraft Status Bot**, ein **Einladungs-Bot** und ein **Outfit-Wettbewerb-Bot**.

## ✨ Neuheiten & Highlights (Aktuelles Update)

In den letzten Updates wurden signifikante Verbesserungen an der Stabilität, Sicherheit und Benutzererfahrung vorgenommen:

*   **🛡️ Live-Moderations-Dashboard:**
    *   **Echtzeit-Überwachung:** Anzeige aller einlaufenden Nachrichten aus Telegram-Gruppen direkt im Web.
    *   **Topic-Support:** Filterung nach Gruppen und spezifischen Topics.
    *   **Remote-Löschen:** Nachrichten können direkt aus dem Dashboard in Telegram gelöscht werden.
    *   **Integriertes Verwarnungssystem:** Nutzer können beim Löschen einer Nachricht direkt verwarnt werden (mit konfigurierbarem Grund und automatischem Bann bei Limit-Erreichung).
*   **🖼️ Telegram Media Proxy:**
    *   **Avatar-Anzeige:** Nutzer-Avatare werden sicher im Dashboard zwischengespeichert und angezeigt.
    *   **Medien-Vorschau:** In Gruppen gesendete Fotos können direkt in der Moderations-Ansicht betrachtet werden.
*   **🔐 Sicheres Login-System:**
    *   **Benutzer-Authentifizierung:** Zugriff auf das Dashboard ist nur noch mit gültigen Zugangsdaten möglich.
    *   **Passwort-Hashing:** Passwörter werden sicher mit modernsten Algorithmen verschlüsselt.
    *   **Rollenbasiert:** Unterscheidung zwischen **Admins** (voller Zugriff) und **Usern** (eingeschränkter Zugriff).
*   **🎮 Erweiterte Bot-Steuerung:**
    *   **Minecraft Status Pro:** Live-Monitoring mit intelligentem Cleanup-System und automatischer Nachrichten-Rotation alle 23 Stunden.
    *   **Quiz & Umfrage Dashboards:** Zentrale Verwaltung von Quizfragen und Umfragen, inklusive Zeitplan-Steuerung und Live-Sende-Funktion.
    *   **Outfit-Wettbewerb Dashboard:** Steuerung von Outfit-Duellen, Gewinner-Auslosung und automatischer Post-Logik.
*   **⚠️ System-Monitoring:**
    *   **Critical Errors Ansicht:** Eine neue Seite im Dashboard zeigt kritische Systemfehler in Echtzeit an, um Probleme sofort zu identifizieren.
    *   **Prozess-Status:** Live-Statusanzeige für alle Bots (Laufend/Gestoppt).

## ✅ Vorgenommene Verbesserungen

*   **Robuste Fehlerbehandlung in `track_activity`:** Sichergestellt, dass bei Fehlern im globalen Activity-Log (`activity_log.jsonl`) die Verarbeitung abbricht, um Inkonsistenzen zu vermeiden.
*   **Asynchrone Dateizugriffe:** Umstellung auf asynchrone Operationen in den Kern-Bots, um Blockaden zu vermeiden.
*   **Optimierter Startprozess:** Alle Bots starten schneller und zuverlässiger; verbesserte Prozesserkennung im Dashboard.
*   **API-Härtung:** Minecraft-Status-Abfragen und Telegram-API-Calls wurden auf Robustheit gegen Timeouts und Fehler optimiert.
*   **Logging & Rotation:** Zentrales Logging mit automatischer Rotation (max 10KB x 5 Files), um Speicherplatz zu sparen.
*   **Caching-Strategie:** Häufig genutzte Konfigurationen werden gecacht, um Festplattenzugriffe zu minimieren.
*   **Refactoring:** Entfernung veralteter Skripte und Konsolidierung von Code-Duplikaten in den Flask-Routen.

## ⛏️ Minecraft Status Bot Features

*   **Live-Monitoring:** Überwacht Java-Minecraft-Server (Spieleranzahl, MOTD, Version, Latenz).
*   **Vollautomatisches Dashboard:** Verwaltung aller IP-Daten, Ports und Topic-IDs direkt über das Web-UI.
*   **Auto-Cleanup:** Der `/player` Befehl löscht seine eigene Antwort automatisch.
*   **Anti-Duplikat:** Globale Locks verhindern Mehrfach-Posts bei API-Verzögerungen.

## 🛡️ NexusMod Bot (Moderation & ID-Finder)

Der NexusMod Bot bleibt dein zentrales Werkzeug für die Gruppenmoderation:

*   **Moderations-Suite:** `/warn`, `/mute`, `/kick`, `/ban` mit flexiblen Zeitangaben.
*   **Chat-Tools:** `/del`, `/purge`, `/pin`, `/unpin`.
*   **Automatisierung:** `/lock` (Sperrung von Links, Medien oder Stickern), Anti-Flood-Schutz und Wortfilter.
*   **Identifikation:** Schnelle Abfrage von IDs mit `/id`, `/chatid`, `/userid` oder `/topicid`.

## 🌐 Zentrales Web-Dashboard

Das Dashboard (Standard-Port 9002) bietet die volle Kontrolle:

1.  **Start/Stop:** Alle Bots können einzeln gestartet und gestoppt werden.
2.  **Live-Moderation:** Direktes Eingreifen in Chat-Verläufe über den Browser.
3.  **Bot-Einstellungen:** Token, IDs, Zeitpläne und Fragenkataloge direkt bearbeiten.
4.  **Benutzerverwaltung:** Admins können Benutzer und deren Berechtigungen verwalten.

---
*Entwickelt für maximale Kontrolle und Transparenz in deiner Telegram-Community.*
