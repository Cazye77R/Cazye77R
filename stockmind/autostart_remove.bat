@echo off
cd /d "%~dp0"
schtasks /Delete /F /TN "StockMind Autopilot"
type nul > data\AUTOPILOT_STOP
echo Autostart entfernt. Ein laufender Autopilot beendet sich innerhalb von ca. 30 Sekunden.
pause
