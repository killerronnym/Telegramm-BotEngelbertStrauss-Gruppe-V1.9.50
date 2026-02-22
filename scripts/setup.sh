#!/bin/bash

# Prüfe, ob Python installiert ist
if ! command -v python3 &> /dev/null
then
    echo "Python 3 ist nicht installiert."
    exit
fi

# Erstelle virtuelle Umgebung
python3 -m venv venv
source venv/bin/activate

# Installiere Abhängigkeiten
pip install -r requirements.txt

# Erstelle Datenbank
python scripts/init_db.py

# Starte Server
python web_dashboard/wsgi.py
