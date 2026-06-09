#!/bin/bash
cd "$(dirname "$0")"

# Python venv prüfen/erstellen
if [ ! -d "venv" ]; then
    echo "Erstelle Python-Umgebung..."
    python3 -m venv venv
fi
source venv/bin/activate

# Dependencies prüfen
pip install -r requirements.txt -q

# Frontend bauen (optional - dist ist bereits vorkompiliert im ZIP enthalten)
if command -v npm &>/dev/null; then
    echo "Frontend wird gebaut..."
    (cd frontend && npm install --prefer-offline -q && npm run build)
else
    echo "npm nicht gefunden - verwende vorkompilierten Build."
fi

# Daten-Ordner
mkdir -p data

echo ""
echo "========================================"
echo "  Toolbox läuft auf http://localhost:8000"
echo "  Beenden: Ctrl+C"
echo "========================================"
echo ""

# Browser nach 4 Sekunden im Hintergrund oeffnen (nach Serverstart)
(sleep 4 && (xdg-open http://localhost:8000 2>/dev/null || open http://localhost:8000 2>/dev/null || true)) &
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
