@echo off
cd /d "%~dp0"

if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

set /p TICKERS=Ticker (mit Leerzeichen, z.B. AAPL MSFT BMW.DE): 
python autopilot.py %TICKERS%

pause
