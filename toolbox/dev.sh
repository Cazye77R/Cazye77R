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

# Frontend Dependencies prüfen
if [ ! -d "frontend/node_modules" ]; then
    echo "Installiere Frontend-Dependencies..."
    cd frontend && npm install && cd ..
fi

# Daten-Ordner
mkdir -p data

echo ""
echo "========================================"
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  Beenden: Ctrl+C"
echo "========================================"
echo ""

# Beim Beenden (Ctrl+C) alle Kind-Prozesse beenden
trap 'kill 0' SIGINT SIGTERM EXIT

# Backend im Hintergrund starten
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &

# Frontend im Vordergrund starten
cd frontend && npm run dev
