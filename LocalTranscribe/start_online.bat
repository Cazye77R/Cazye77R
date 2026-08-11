@echo off
:: Einrichten und starten: installiert Pakete und laedt die benoetigten Modelle.
:: Braucht Internet. Danach genuegt start_offline.bat.
cd /d "%~dp0"
python launcher.py --setup
pause
