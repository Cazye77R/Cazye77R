@echo off
REM Startet agent-office (React/Vite Dev-Server)
REM Verwendung: Doppelklick auf start.bat  oder  start.bat im Terminal

cd /d "%~dp0agent-office"

if not exist node_modules (
    echo ^>^> npm install ...
    npm install
)

echo ^>^> npm run dev
npm run dev
pause
