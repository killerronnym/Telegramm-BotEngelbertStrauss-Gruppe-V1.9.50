import sys
import os

# Füge das Elternverzeichnis (Projekt-Root) zum Python-Pfad hinzu
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_dashboard.app import create_app

app = create_app()

if __name__ == "__main__":
    # Wir verwenden Port 9002, da die Logs zeigen, dass der Server dort startet.
    port = int(os.environ.get("PORT", 9002))
    app.run(host="0.0.0.0", port=port, debug=True)
