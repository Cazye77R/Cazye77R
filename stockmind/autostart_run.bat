@echo off
cd /d "%~dp0"
if not exist "data" mkdir data
call .venv\Scripts\activate.bat
python autopilot.py >> data\autopilot.log 2>&1
