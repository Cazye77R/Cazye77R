#!/bin/bash
echo "=== Toolbox wird gestartet ==="
cd "$(dirname "$0")"
mkdir -p data
if [ ! -d "frontend/dist" ]; then
    echo "Frontend wird gebaut..."
    cd frontend && npm install && npm run build && cd ..
fi
echo "Starte Server auf http://localhost:8000"
xdg-open http://localhost:8000 2>/dev/null || open http://localhost:8000 2>/dev/null || true
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
