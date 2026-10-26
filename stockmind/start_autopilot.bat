@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Lege Python-Umgebung an...
    python -m venv .venv
    if errorlevel 1 (
        echo Python wurde nicht gefunden. Bitte Python 3.11+ installieren.
        pause
        exit /b 1
    )
)
call .venv\Scripts\activate.bat
set PIP_DISABLE_PIP_VERSION_CHECK=1

rem Nur installieren, wenn sich requirements.txt seit der letzten Installation geaendert hat.
rem --no-cache-dir: umgeht einen beschaedigten pip-Cache ("Cache entry deserialization failed").
fc /b requirements.txt .venv\installed-requirements.txt >nul 2>&1
if errorlevel 1 (
    echo Installiere Abhaengigkeiten...
    python -m pip install --quiet --no-cache-dir --upgrade pip
    python -m pip install --quiet --no-cache-dir -r requirements.txt
    if errorlevel 1 (
        echo Installation fehlgeschlagen.
        pause
        exit /b 1
    )
    copy /y requirements.txt .venv\installed-requirements.txt >nul
)

set /p TICKERS=Ticker (mit Leerzeichen, z.B. AAPL MSFT BMW.DE): 
python autopilot.py %TICKERS%

pause
