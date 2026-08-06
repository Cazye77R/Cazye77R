@echo off
REM HandCursor launcher for Windows.
REM   start.bat            interactive menu
REM   start.bat ui         Streamlit interface
REM   start.bat app        OpenCV window
REM   start.bat --help     all options
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 run.py %*
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        python run.py %*
    ) else (
        echo Python 3 wurde nicht gefunden. Bitte Python 3.10-3.12 installieren.
        echo Download: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

if errorlevel 1 pause
endlocal
