@echo off
setlocal EnableDelayedExpansion

echo.
echo  ============================================================
echo   SecondBrain Agent - Installation
echo  ============================================================
echo.

REM ── Check Python ─────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [FEHLER] Python nicht gefunden!
    echo.
    echo  Bitte Python 3.10 oder neuer installieren:
    echo  https://www.python.org/downloads/
    echo.
    echo  Wichtig: "Add Python to PATH" beim Setup anhaeken!
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do (
    echo  Gefunden: %%v
    REM Extract minor version to warn if < 3.10
    for /f "tokens=2 delims=." %%m in ("%%v") do set MINOR=%%m
)

REM ── pip upgrade ──────────────────────────────────────────────
echo.
echo  [1/3] Aktualisiere pip...
python -m pip install --quiet --upgrade pip
echo  OK

REM ── Install requirements ─────────────────────────────────────
echo.
echo  [2/3] Installiere Pakete aus requirements.txt...
echo  (Das kann einige Minuten dauern)
echo.
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo  [FEHLER] Installation fehlgeschlagen!
    echo  Versuche: pip install -r requirements.txt
    pause
    exit /b 1
)

REM ── Initialize DB ────────────────────────────────────────────
echo.
echo  [3/3] Initialisiere Datenbank...
python -c "from core.database import init_db; init_db(); print('  OK')"
if %errorlevel% neq 0 (
    echo  [WARNUNG] Datenbank-Init fehlgeschlagen - wird beim ersten Start erneut versucht.
)

REM ── Done ─────────────────────────────────────────────────────
echo.
echo  ============================================================
echo   Installation abgeschlossen!
echo.
echo   Naechste Schritte:
echo   1. Ollama installieren:  https://ollama.ai
echo   2. Modelle laden:
echo        ollama pull llama3
echo        ollama pull nomic-embed-text
echo   3. App starten:
echo        python launcher.py
echo  ============================================================
echo.
pause
