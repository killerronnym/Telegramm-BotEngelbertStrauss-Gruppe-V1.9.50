# Security / Secrets Policy

## Regeln
- **Niemals** Geheimnisse (Tokens, Passwörter, API-Keys, private Keys) committen.
- Nutze Umgebungsvariablen und eine lokale `.env` Datei.
- Konfigurationsdateien, die umgebungsspezifische Werte enthalten, dürfen nur als `*.example.*` committet werden.

## Incident Response
Falls Geheimnisse versehentlich committet wurden:
1. Geheimnisse sofort widerrufen/ändern (Rotate).
2. Den Commit aus der Git-Historie entfernen (z. B. mit `git filter-repo` oder BFG Repo-Cleaner).
3. Den Vorfall im Team melden.

## Branch Protection
Es wird empfohlen, Branch Protection für `main` zu aktivieren:
- "Require status checks to pass before merging" (Gitleaks muss grün sein).
- "Restrict who can push to matching branches".
