@echo off
REM ===================================================================
REM  Live Kamera-Erkennung & Koerper-Tracking - Starter fuer Windows
REM
REM  Einfach doppelklicken. Beim ersten Start werden die benoetigten
REM  Pakete nach Rueckfrage in eine eigene Umgebung (.venv) installiert.
REM
REM  Konsolentexte sind bewusst ASCII-only: die Windows-Konsole nutzt je
REM  nach System cp850/cp437, wo Umlaute als Zeichensalat erscheinen.
REM ===================================================================
chcp 65001 >nul 2>&1
title Kamera-Erkennung
cd /d "%~dp0"

echo.
echo  ============================================
echo    Live Kamera-Erkennung ^& Koerper-Tracking
echo  ============================================
echo.

REM ---- Python suchen ------------------------------------------------
REM "-c import sys" statt "--version": der Microsoft-Store-Platzhalter
REM von Windows wuerde bei --version faelschlich als Erfolg durchgehen.
set "PY="

py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto :python_gefunden

python -c "import sys" >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto :python_gefunden

echo  FEHLER: Es wurde keine Python-Installation gefunden.
echo.
echo  Bitte Python 3.10 oder neuer installieren:
echo      https://www.python.org/downloads/
echo.
echo  WICHTIG: Im Installer unten "Add python.exe to PATH" ankreuzen,
echo           sonst wird Python hier nicht gefunden.
echo.
pause
exit /b 1

:python_gefunden
set "VENV_PY=%CD%\.venv\Scripts\python.exe"

REM ---- Ist alles startklar? ----------------------------------------
if not exist "%VENV_PY%" goto :installation
"%VENV_PY%" -c "import streamlit, streamlit_webrtc, av, cv2, ultralytics, mediapipe" >nul 2>&1
if errorlevel 1 goto :installation
goto :starten

REM ---- Erstinstallation (mit Rueckfrage) ---------------------------
:installation
echo  Die benoetigten Pakete sind noch nicht installiert.
echo.
echo  Es werden ca. 2-3 GB heruntergeladen (torch, ultralytics,
echo  mediapipe, streamlit ...). Das dauert je nach Verbindung
echo  einige Minuten.
echo.
echo  Die Installation erfolgt isoliert im Unterordner .venv und
echo  laesst deine System-Python-Installation unveraendert.
echo.

set "ANTWORT="
set /p "ANTWORT=Jetzt installieren? [J/n] "
if /i "%ANTWORT%"=="n"    goto :abbruch
if /i "%ANTWORT%"=="nein" goto :abbruch

if exist "%VENV_PY%" goto :venv_vorhanden
echo.
echo  ==^> Erstelle virtuelle Umgebung .venv
%PY% -m venv .venv
if errorlevel 1 goto :venv_fehler
:venv_vorhanden

echo.
echo  ==^> Aktualisiere pip
"%VENV_PY%" -m pip install --upgrade pip

echo.
echo  ==^> Installiere Pakete
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :install_fehler

echo.
echo  ==^> Installation abgeschlossen
echo.

REM ---- App starten -------------------------------------------------
REM "-m streamlit" ist wichtig: nur so liegt der Projektordner auf dem
REM Python-Suchpfad. Mit dem blossen "streamlit"-Befehl findet Python
REM das Paket camera_detection nicht.
:starten
echo  ==^> Starte Kamera-Erkennung
echo      Der Browser oeffnet sich gleich automatisch.
echo      Beenden: dieses Fenster schliessen oder Strg+C druecken.
echo.
"%VENV_PY%" -m streamlit run camera_detection\app.py %*
set "CODE=%ERRORLEVEL%"

if not "%CODE%"=="0" (
    echo.
    echo  Die App wurde mit Fehlercode %CODE% beendet.
    echo  Die Meldung oberhalb nennt die Ursache.
    echo.
    pause
)
exit /b %CODE%

REM ---- Fehlerpfade -------------------------------------------------
REM Ueberall "pause", sonst verschwindet das Fenster beim Doppelklick
REM sofort wieder und die Meldung ist nicht lesbar.
:abbruch
echo.
echo  Abgebrochen. Es wurde nichts installiert und nichts veraendert.
echo.
pause
exit /b 0

:venv_fehler
echo.
echo  FEHLER: Die virtuelle Umgebung .venv konnte nicht erstellt werden.
echo.
echo  Moegliche Ursachen:
echo    - kein Schreibrecht in diesem Ordner
echo    - Python-Installation unvollstaendig (venv-Modul fehlt)
echo.
pause
exit /b 1

:install_fehler
echo.
echo  FEHLER: Die Installation der Pakete ist fehlgeschlagen.
echo.
echo  Pruefe die Internetverbindung und starte danach erneut.
echo  Bleibt der Fehler bestehen, hilft oft: den Ordner .venv
echo  loeschen und noch einmal doppelklicken.
echo.
pause
exit /b 1
