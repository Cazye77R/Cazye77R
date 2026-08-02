@echo off
echo ToolHub wird gestartet...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python ist nicht installiert. Bitte installiere Python 3.10+
    pause
    exit /b 1
)
pip install -r requirements.txt --quiet
start http://localhost:8800
python server.py
