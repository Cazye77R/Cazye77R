@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  LOCAL-FILE-SORTER  --  Setup und Start (Windows)
:: ============================================================

set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%.venv"

echo.
echo  ============================================
echo   LOCAL-FILE-SORTER  --  Setup und Start
echo  ============================================
echo.

:: ---- 1. Python suchen ----------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo [FEHLER] Python wurde nicht gefunden.
    echo          Lade Python 3.11+ von https://www.python.org/downloads/
    echo          Stelle sicher, dass "Add python.exe to PATH" aktiv ist.
    pause
    exit /b 1
)

:: Python-Version direkt prüfen (kein String-Parsing, kein Delimiter-Problem)
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>nul
if errorlevel 1 (
    echo [FEHLER] Python zu alt ^(Mindestversion: 3.11^).
    echo          Lade aktuelles Python: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "delims=" %%V in ('python -c "import sys; print(sys.version.split()[0])" 2^>nul') do set "PY_VER=%%V"
echo [OK] Python !PY_VER! gefunden.

:: ---- 2. tkinter prüfen ---------------------------------------
python -c "import tkinter" 2>nul
if errorlevel 1 (
    echo [FEHLER] tkinter ist nicht verfuegbar.
    echo          Fuehre den Python-Installer erneut aus und aktiviere
    echo          "tcl/tk and IDLE".
    pause
    exit /b 1
)
echo [OK] tkinter verfuegbar.

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

:: ---- 4. Venv aktivieren und pip aktualisieren -----------------
call "%VENV_DIR%\Scripts\activate.bat"
echo [..] pip aktualisieren ...
python -m pip install --upgrade pip --quiet
echo [OK] pip aktuell.

:: ---- 5. Abhaengigkeiten installieren -------------------------
echo [..] Abhaengigkeiten installieren ...
pip install -r "%SCRIPT_DIR%requirements.txt" --quiet
if errorlevel 1 (
    echo [FEHLER] Installation fehlgeschlagen.
    echo          Pruefe deine Internetverbindung und versuche es erneut.
    pause
    exit /b 1
)
echo [OK] Alle Abhaengigkeiten installiert.

:: ---- 6. Ollama prüfen (Hinweis, kein Abbruch) ----------------
curl -s --connect-timeout 2 http://localhost:11434 >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNUNG] Ollama laeuft nicht auf localhost:11434.
    echo           Starte Ollama und lade das Modell:
    echo             ollama pull qwen2.5:7b-instruct-q4_K_M
    echo           Das Programm startet trotzdem.
    echo.
) else (
    echo [OK] Ollama erreichbar.
)

:: ---- 7. Programm starten -------------------------------------
echo [..] Starte LOCAL-FILE-SORTER ...
echo.
cd /d "%SCRIPT_DIR%"
python main.py
if errorlevel 1 (
    echo.
    echo [FEHLER] Programm mit Fehlercode beendet.
    pause
)

endlocal
