@echo off
setlocal

cd /d "%~dp0"

:: Sicherstellen dass die virtuelle Umgebung existiert
if not exist ".venv\Scripts\python.exe" (
    echo FEHLER: Keine virtuelle Umgebung gefunden.
    echo Bitte zuerst "start_online.bat" ausfuehren um alles einzurichten.
    pause
    exit /b 1
)

:: App direkt starten – kein Internet erforderlich
echo Starte LocalTranscribe (Offline-Modus)...
.venv\Scripts\python.exe -m streamlit run app.py

pause
