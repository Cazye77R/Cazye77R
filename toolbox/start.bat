@echo off
echo === Toolbox wird gestartet ===
cd /d "%~dp0"
if not exist "data" mkdir data
if not exist "frontend\dist" (
    echo Frontend wird gebaut...
    cd frontend && npm install && npm run build && cd ..
)
echo Starte Server auf http://localhost:8000
start http://localhost:8000
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
pause
