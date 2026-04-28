@echo off
setlocal EnableDelayedExpansion

echo.
echo  ============================================================
echo   SecondBrain Agent - EXE Build
echo  ============================================================
echo.

REM ── Verify Python ────────────────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [FEHLER] Python nicht gefunden!
    echo  Bitte Python 3.10+ installieren: https://python.org
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version') do echo  Python: %%v

REM ── Install / upgrade PyInstaller ────────────────────────────
echo.
echo  [1/4] PyInstaller wird installiert / aktualisiert...
pip install --quiet --upgrade pyinstaller
if %errorlevel% neq 0 (
    echo  [FEHLER] PyInstaller konnte nicht installiert werden.
    pause
    exit /b 1
)
echo  OK

REM ── Install app dependencies ─────────────────────────────────
echo.
echo  [2/4] App-Abhaengigkeiten werden installiert...
pip install --quiet -r requirements.txt
if %errorlevel% neq 0 (
    echo  [WARNUNG] Einige Pakete konnten nicht installiert werden.
    echo  Build wird trotzdem fortgesetzt...
)
echo  OK

REM ── Clean previous build ─────────────────────────────────────
echo.
echo  [3/4] Bereinige alten Build...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
echo  OK

REM ── Run PyInstaller ──────────────────────────────────────────
echo.
echo  [4/4] Baue EXE (das kann 2-5 Minuten dauern)...
echo.
pyinstaller second_brain.spec --clean --noconfirm
if %errorlevel% neq 0 (
    echo.
    echo  [FEHLER] Build fehlgeschlagen! Siehe Ausgabe oben.
    pause
    exit /b 1
)

REM ── Result ───────────────────────────────────────────────────
echo.
echo  ============================================================
echo   Build erfolgreich!
echo.
if exist dist\SecondBrain.exe (
    for %%f in (dist\SecondBrain.exe) do (
        set SIZE=%%~zf
        set /a SIZE_MB=!SIZE! / 1048576
        echo   Datei: dist\SecondBrain.exe
        echo   Groesse: ~!SIZE_MB! MB
    )
) else (
    echo   EXE nicht gefunden - pruefe dist\ Ordner manuell.
)
echo  ============================================================
echo.
pause
