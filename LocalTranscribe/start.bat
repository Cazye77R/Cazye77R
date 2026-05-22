@echo off
setlocal

cd /d "%~dp0"

:: 1. Virtuelle Umgebung erstellen (nur beim ersten Start)
if not exist ".venv\Scripts\python.exe" (
    echo Erstelle virtuelle Umgebung...
    python -m venv .venv
    if errorlevel 1 (
        echo FEHLER: Python nicht gefunden. Bitte Python 3.10+ installieren.
        pause
        exit /b 1
    )
)

:: 2. Abhaengigkeiten installieren / aktualisieren
echo Installiere Abhaengigkeiten...
.venv\Scripts\python.exe -m pip install --quiet --no-cache-dir --upgrade pip
.venv\Scripts\python.exe -m pip install --quiet --no-cache-dir -r requirements.txt

:: 3. App starten
echo Starte LocalTranscribe...
.venv\Scripts\python.exe -m streamlit run app.py

pause
