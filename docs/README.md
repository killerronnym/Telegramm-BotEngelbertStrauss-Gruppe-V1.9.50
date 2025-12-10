# Telegramm-Bot-Ökosystem: NexusMod & Co.

Willkommen zu deinem persönlichen Telegramm-Bot-Control-Panel! Dieses Projekt bietet eine zentrale Verwaltungsoberfläche für mehrere spezialisierte Telegram-Bots, darunter der leistungsstarke **NexusMod Bot** (ehemals ID-Finder Bot) für umfassende Moderationsaufgaben, ein Einladungs-Bot und ein Outfit-Wettbewerb-Bot.

## ✨ Hauptfunktionen des NexusMod Bots (ID-Finder & Moderation)

Der NexusMod Bot ist dein ultimatives Werkzeug für die Telegram-Gruppenverwaltung, ausgestattet mit einer Vielzahl an Moderations- und Schutzfunktionen:

*   **Umfassende Moderationswerkzeuge:** Von flexiblen Verwarnungen (`/warn`, `/unwarn`, `/clearwarnings`) über präzise Stummschaltungen (`/mute`, `/unmute`) bis hin zu effektiven Kick- und Bann-Optionen (`/kick`, `/ban`, `/unban`).
*   **Nachrichten-Moderation:** Lösche einzelne Nachrichten (`/del`) oder bereinige ganze Chat-Verläufe (`/purge`). Pinne wichtige Nachrichten (`/pin`, `/unpin`) und sperre bestimmte Inhalte wie Medien oder Links (`/lock`, `/unlock`).
*   **Starke Auto-Moderation:**
    *   **Anti-Flood:** Verhindert das Überfluten des Chats mit Nachrichten (`/setflood`).
    *   **Link-Kontrolle:** Lege fest, wie mit Links verfahren werden soll (erlauben, verwarnen, stummschalten, bannen) (`/setlinkmode`).
    *   **Wortfilter:** Automatische Filterung und Aktion bei unerwünschten Wörtern (`/blacklist`).
*   **Flexibles Rollensystem:** Definiere benutzerdefinierte Rollen und weise Moderatoren eingeschränkte Berechtigungen zu (`/mod add`, `/mod remove`, `/setrole`).
*   **Zentrale Weboberfläche:** Verwalte alle Einstellungen, starte/stoppe Bots und sieh dir detaillierte Logs über ein intuitives Web-Dashboard an.
*   **Intelligente Log-Verwaltung:** Getrennte Logs für Befehlsausführungen und Systemfehler, optional in ein spezielles Telegram-Topic postbar.
*   **ID-Finder-Funktionalität:** Rufe Chat-IDs, User-IDs und Topic-IDs direkt im Chat ab (`/chatid`, `/userid`, `/topicid`, `/id`).

## 🚀 Installation & Start

Eine detaillierte Installationsanleitung findest du in der [INSTALL.md](INSTALL.md) Datei. Sie führt dich durch die Schritte zum Klonen des Repositorys, zur Installation der Abhängigkeiten und zur Konfiguration der Bots über das Web-Dashboard.

## 🌐 Web-Dashboard Übersicht

Das Web-Dashboard (erreichbar unter `http://localhost:8080/id-finder` nach dem Start) bietet dir eine zentrale Steuerzentrale:

*   **Statusanzeige:** Sieh auf einen Blick, ob der Bot läuft oder gestoppt ist.
*   **Konfiguration:** Gib Bot-Tokens, Haupt-Gruppen-IDs und optionale Log-Topic-IDs ein.
*   **Steuerung:** Starte, stoppe und speichere die Bot-Konfiguration direkt über Buttons.
*   **Zwei Logbücher:** Überwache Befehlsausführungen und Systemfehler in getrennten, übersichtlichen Log-Fenstern.
*   **Befehls-Dokumentation:** Ein Link führt dich zu einer detaillierten Übersicht aller Bot-Befehle mit Erklärungen.

## 📋 Befehlsübersicht (NexusMod Bot)

Hier ist eine Zusammenfassung der Befehle. Für detaillierte Erklärungen besuche das Web-Dashboard oder die Befehls-Dokumentation.

---

### **Basis-Moderation**
*   `/warn @user [Grund]`
    *   *Erklärung:* Gibt eine Verwarnung.
*   `/warnings @user`
    *   *Erklärung:* Zeigt aktuelle Verwarnungen.
*   `/unwarn @user`
    *   *Erklärung:* Entfernt eine Verwarnung.
*   `/clearwarnings @user`
    *   *Erklärung:* Setzt Verwarnungen zurück.
*   `/mute @user 10m [Grund]`
    *   *Erklärung:* Stummschalten für Dauer (z. B. 10m, 2h, 1d).
*   `/unmute @user`
    *   *Erklärung:* Stummschaltung aufheben.
*   `/ban @user [Grund]`
    *   *Erklärung:* Bann aus der Gruppe.
*   `/unban @user`
    *   *Erklärung:* Bann aufheben.
*   `/kick @user [Grund]`
    *   *Erklärung:* Entfernt Nutzer (kann direkt wieder beitreten, je nach Einstellung).

### **Nachrichten- und Chat-Management**
*   `/del`
    *   *Erklärung:* Löscht die Nachricht, auf die geantwortet wurde.
*   `/purge`
    *   *Erklärung:* Löscht mehrere Nachrichten ab der beantworteten Nachricht bis zur aktuellen.
*   `/pin`
    *   *Erklärung:* Pinnt die beantwortete Nachricht.
*   `/unpin`
    *   *Erklärung:* Entfernt Pin.
*   `/lock [feature]`
    *   *Erklärung:* Sperrt z. B. Medien/Links/Sticker. Beispiele: `/lock links`, `/lock media`
*   `/unlock [feature]`
    *   *Erklärung:* Hebt die Sperre auf.

### **Anti-Spam / Auto-Moderation**
*   `/antispam on|off`
    *   *Erklärung:* Aktiviert/Deaktiviert Spam-Schutz.
*   `/setflood 5`
    *   *Erklärung:* Max. Nachrichten in kurzer Zeit.
*   `/setlinkmode allow|warn|mute|ban`
    *   *Erklärung:* Wie Links behandelt werden.
*   `/blacklist add [wort]`
    *   *Erklärung:* Verbietet Wörter/Patterns.
*   `/blacklist remove [wort]`
*   `/blacklist list`

### **Rollen & Rechte**
*   `/adminlist`
    *   *Erklärung:* Zeigt Admins (optional inkl. Bot-Rollenlogik).
*   `/mod add @user`
    *   *Erklärung:* Fügt Bot-interne Moderatoren hinzu.
*   `/mod remove @user`
*   `/permissions`
    *   *Erklärung:* Zeigt Bot-Rechte/Feature-Flags.
*   `/setrole @user admin|mod|trusted|user`
    *   *Erklärung:* Bot-eigenes Rollensystem.

### **Nützlich für deine Entwickler-Praxis**
*   `/chatid`
    *   *Erklärung:* Gibt die Chat-ID aus.
*   `/userid`
    *   *Erklärung:* Gibt die User-ID aus (eigene oder per Reply).
*   `/topicid`
    *   *Erklärung:* Gibt die Topic-/Thread-ID aus (wenn Forum-Topics genutzt werden).
*   `/id`
    *   *Erklärung:* Kombi-Ausgabe: User, Chat, Topic.

---

## 🤝 Beitrag & Entwicklung

Dieses Projekt ist für die private Nutzung gedacht. Änderungen und Erweiterungen können über das integrierte Code-Panel vorgenommen werden.
