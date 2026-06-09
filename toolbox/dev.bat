@echo off
title Toolbox Dev
cd /d "%~dp0"

REM Python venv prüfen/erstellen
if not exist "venv" (
    echo Erstelle Python-Umgebung...
    python -m venv venv
)
call venv\Scripts\activate

REM Dependencies prüfen
pip install -r requirements.txt -q

REM Frontend Dependencies prüfen
if not exist "frontend\node_modules" (
    echo Installiere Frontend-Dependencies...
    cd frontend && npm install && cd ..
)

REM Daten-Ordner
if not exist "data" mkdir data

echo.
echo ========================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   Beenden: Ctrl+C oder Fenster schliessen
echo ========================================
echo.

REM Backend in neuem Fenster starten (nutzt Python aus dem venv direkt)
start "Toolbox Backend" cmd /k "cd /d "%~dp0" && venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

REM Frontend im aktuellen Fenster starten
cd frontend && npm run dev
