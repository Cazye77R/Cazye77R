@echo off
title Toolbox
cd /d "%~dp0"

REM Python venv prüfen/erstellen
if not exist "venv" (
    echo Erstelle Python-Umgebung...
    python -m venv venv
)
call venv\Scripts\activate

REM Dependencies prüfen
pip install -r requirements.txt -q

REM Frontend bauen wenn nötig
if not exist "frontend\dist\index.html" (
    echo Frontend wird gebaut...
    cd frontend && npm install && npm run build && cd ..
)

REM Daten-Ordner
if not exist "data" mkdir data

echo.
echo ========================================
echo   Toolbox laeuft auf http://localhost:8000
echo   Beenden: Ctrl+C
echo ========================================
echo.
start http://localhost:8000
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
