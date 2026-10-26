@echo off
cd /d "%~dp0"
echo === StockMind Autopilot: Autostart einrichten ===
set /p TICKERS=Ticker (mit Leerzeichen, z.B. AAPL MSFT BMW.DE): 

if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --quiet -r requirements.txt
python autopilot.py %TICKERS% --save-tickers --once
if errorlevel 1 (
    echo Testlauf fehlgeschlagen - Autostart NICHT eingerichtet.
    pause
    exit /b 1
)

schtasks /Create /F /SC ONLOGON /TN "StockMind Autopilot" /TR "\"%~dp0autostart_run.bat\"" /RL LIMITED
if errorlevel 1 (
    echo Aufgabe konnte nicht angelegt werden.
    pause
    exit /b 1
)
echo.
echo Fertig: Der Autopilot startet ab jetzt bei jeder Anmeldung (Log: data\autopilot.log).
echo Entfernen: autostart_remove.bat
pause
