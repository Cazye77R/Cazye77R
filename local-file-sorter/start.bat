@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

:: ============================================================
::  LOCAL-FILE-SORTER  –  Setup & Start (Windows)
:: ============================================================

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"
set "PYTHON_MIN_MAJOR=3"
set "PYTHON_MIN_MINOR=11"

echo.
echo  ============================================
echo   LOCAL-FILE-SORTER  //  Setup ^& Start
echo  ============================================
echo.

:: ---- 1. Python prüfen ----------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python wurde nicht gefunden.
    echo          Lade Python 3.11+ von https://www.python.org/downloads/
    echo          Stelle sicher, dass "Add python.exe to PATH" aktiviert ist.
    pause
    exit /b 1
)

for /f "tokens=1,2 delims=." %%A in ('python -c "import sys; print(sys.version_info.major, sys.version_info.minor)" 2^>nul') do (
    set "PY_MAJOR=%%A"
    set "PY_MINOR=%%B"
)

if !PY_MAJOR! LSS %PYTHON_MIN_MAJOR% goto :py_too_old
if !PY_MAJOR! EQU %PYTHON_MIN_MAJOR% if !PY_MINOR! LSS %PYTHON_MIN_MINOR% goto :py_too_old
echo [OK] Python !PY_MAJOR!.!PY_MINOR! gefunden.
goto :py_ok

:py_too_old
echo [FEHLER] Python !PY_MAJOR!.!PY_MINOR! ist zu alt.
echo          Mindestversion: %PYTHON_MIN_MAJOR%.%PYTHON_MIN_MINOR%
echo          Lade aktuelles Python von https://www.python.org/downloads/
pause
exit /b 1

:py_ok

:: ---- 2. tkinter prüfen ---------------------------------------
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] tkinter ist nicht verfügbar.
    echo          Führe den Python-Installer erneut aus und aktiviere
    echo          "tcl/tk and IDLE".
    pause
    exit /b 1
)
echo [OK] tkinter verfügbar.

:: ---- 3. Virtuelle Umgebung ------------------------------------
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [OK] Virtuelle Umgebung bereits vorhanden.
) else (
    echo [..] Erstelle virtuelle Umgebung ...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [FEHLER] Virtuelle Umgebung konnte nicht erstellt werden.
        pause
        exit /b 1
    )
    echo [OK] Virtuelle Umgebung erstellt.
)

:: ---- 4. Venv aktivieren & pip aktualisieren -------------------
call "%VENV_DIR%\Scripts\activate.bat"
echo [..] pip aktualisieren ...
python -m pip install --upgrade pip --quiet
echo [OK] pip aktuell.

:: ---- 5. Abhängigkeiten installieren ---------------------------
echo [..] Abhängigkeiten installieren ...
pip install -r "%SCRIPT_DIR%requirements.txt" --quiet
if errorlevel 1 (
    echo [FEHLER] Installation der Abhängigkeiten fehlgeschlagen.
    echo          Prüfe deine Internetverbindung und versuche es erneut.
    pause
    exit /b 1
)
echo [OK] Alle Abhängigkeiten installiert.

:: ---- 6. Ollama prüfen (nur Hinweis, kein Abbruch) -------------
curl -s --connect-timeout 2 http://localhost:11434 >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNUNG] Ollama läuft nicht auf localhost:11434.
    echo           Starte Ollama und lade das Modell:
    echo             ollama pull qwen2.5:7b-instruct-q4_K_M
    echo           Das Programm startet trotzdem, Pläne können aber
    echo           erst generiert werden wenn Ollama erreichbar ist.
    echo.
) else (
    echo [OK] Ollama erreichbar.
)

:: ---- 7. Programm starten --------------------------------------
echo [..] Starte LOCAL-FILE-SORTER ...
echo.
cd /d "%SCRIPT_DIR%"
python main.py
if errorlevel 1 (
    echo.
    echo [FEHLER] Programm mit Fehlercode %errorlevel% beendet.
    pause
)

endlocal
