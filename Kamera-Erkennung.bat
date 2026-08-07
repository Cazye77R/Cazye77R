@echo off
REM ===================================================================
REM  Live Kamera-Erkennung & Koerper-Tracking - Starter fuer Windows
REM
REM  Einfach doppelklicken. Beim ersten Start werden die benoetigten
REM  Pakete nach Rueckfrage in eine eigene Umgebung (.venv) installiert.
REM
REM  Benoetigt Python 3.10 - 3.12. Neuere Versionen (3.13, 3.14) gehen
REM  NICHT: fuer sie gibt es kein fertiges mediapipe-Paket, und ein Bau
REM  aus dem Quelltext ist auf Windows nicht praktikabel.
REM
REM  Konsolentexte sind bewusst ASCII-only: die Windows-Konsole nutzt je
REM  nach System cp850/cp437, wo Umlaute als Zeichensalat erscheinen.
REM ===================================================================
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title Kamera-Erkennung
cd /d "%~dp0"

REM Obergrenze < 3.13 von mediapipe, Untergrenze >= 3.10 von streamlit /
REM streamlit-webrtc / aiortc (alle deklarieren requires_python >= 3.10).
set "VERSION_TEST=import sys; sys.exit(0 if (3,10) <= sys.version_info < (3,13) else 1)"

echo.
echo  ============================================
echo    Live Kamera-Erkennung ^& Koerper-Tracking
echo  ============================================
echo.

set "WINGET_VERSUCHT="

REM ---- Passenden Python-Interpreter suchen -------------------------
:suche_python
set "PY="

REM Gezielt nach unterstuetzten Versionen fragen. Der py-Launcher waehlt
REM damit die richtige, auch wenn zusaetzlich ein zu neues Python da ist.
for %%V in (3.12 3.11 3.10) do (
    if not defined PY (
        py -%%V -c "%VERSION_TEST%" >nul 2>&1
        if not errorlevel 1 set "PY=py -%%V"
    )
)
if defined PY goto :python_gefunden

REM Fallback: "python" aus dem PATH - aber nur, wenn die Version passt.
REM "-c" statt "--version", sonst geht der Microsoft-Store-Platzhalter
REM faelschlich als funktionierendes Python durch.
python -c "%VERSION_TEST%" >nul 2>&1
if not errorlevel 1 set "PY=python"
if defined PY goto :python_gefunden

goto :kein_python

:python_gefunden
for /f "delims=" %%I in ('%PY% -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "PYVER=%%I"
for /f "delims=" %%I in ('%PY% -c "import sys;print(sys.executable)" 2^>nul') do set "PYEXE=%%I"
echo  Verwende Python !PYVER!
echo  ^(!PYEXE!^)
echo.

set "VENV_PY=%CD%\.venv\Scripts\python.exe"

REM ---- Vorhandene .venv auf passende Version pruefen ---------------
REM Wurde die Umgebung frueher mit einem zu neuen Python gebaut, ist sie
REM unbrauchbar - ohne diese Pruefung liefe jeder Start wieder hinein.
if not exist "%VENV_PY%" goto :installation
"%VENV_PY%" -c "%VERSION_TEST%" >nul 2>&1
if not errorlevel 1 goto :venv_ok

for /f "delims=" %%I in ('"%VENV_PY%" -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "ALTVER=%%I"
echo  Die vorhandene Umgebung .venv wurde mit Python !ALTVER! erstellt.
echo  Diese Version wird nicht unterstuetzt - die Umgebung muss neu
echo  aufgebaut werden.
echo.
set "ANTWORT="
set /p "ANTWORT=.venv jetzt loeschen und neu erstellen? [J/n] "
if /i "!ANTWORT!"=="n"    goto :abbruch
if /i "!ANTWORT!"=="nein" goto :abbruch
echo.
echo  ==^> Entferne alte Umgebung
rmdir /s /q ".venv"
goto :installation

:venv_ok
REM ---- Sind alle Pakete da? ----------------------------------------
"%VENV_PY%" -c "import streamlit, streamlit_webrtc, av, cv2, ultralytics, mediapipe" >nul 2>&1
if errorlevel 1 goto :installation
goto :starten

REM ---- Installation / Aktualisierung (mit Rueckfrage) --------------
:installation
if exist "%VENV_PY%" (
    echo  Es fehlen Pakete oder sie sind nicht auf dem passenden Stand.
    echo  Die vorhandene Umgebung .venv wird aktualisiert.
) else (
    echo  Die benoetigten Pakete sind noch nicht installiert.
    echo  Die Installation erfolgt isoliert im Unterordner .venv und
    echo  laesst deine System-Python-Installation unveraendert.
)
echo.
echo  Es werden bis zu ca. 2-3 GB heruntergeladen (torch, ultralytics,
echo  mediapipe, streamlit ...). Das dauert je nach Verbindung
echo  einige Minuten.
echo.

set "ANTWORT="
set /p "ANTWORT=Jetzt fortfahren? [J/n] "
if /i "!ANTWORT!"=="n"    goto :abbruch
if /i "!ANTWORT!"=="nein" goto :abbruch

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
REM --upgrade, damit ein bereits vorhandener, zu alter Paketstand aktiv
REM hochgezogen wird statt stehen zu bleiben.
REM --only-binary fuer die kompilierten Pakete: fehlt ein fertiges Wheel,
REM bricht pip sofort verstaendlich ab, statt einen aussichtslosen
REM Compiler-Lauf zu starten (genau das erzeugte die MSVC-Fehlermeldung).
"%VENV_PY%" -m pip install --upgrade --only-binary=av,mediapipe,torch,opencv-contrib-python -r requirements.txt
if errorlevel 1 goto :install_fehler

REM Nach der Installation gegenpruefen. Ohne diesen Schritt wuerde ein
REM unvollstaendiger Paketstand erst als roher Python-Traceback auffallen.
echo.
echo  ==^> Pruefe Installation
"%VENV_PY%" -c "import streamlit, streamlit_webrtc, av, cv2, ultralytics, mediapipe" 2>&1
if errorlevel 1 goto :pruefung_fehler

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
set "CODE=!ERRORLEVEL!"

if not "!CODE!"=="0" (
    echo.
    echo  Die App wurde mit Fehlercode !CODE! beendet.
    echo  Die Meldung oberhalb nennt die Ursache.
    echo.
    pause
)
exit /b !CODE!

REM ---- Kein passendes Python ---------------------------------------
:kein_python
echo  Kein passendes Python gefunden.

REM Ist ueberhaupt ein Python da? Dann die Version nennen - der Nutzer
REM soll verstehen, warum eine vorhandene Installation nicht reicht.
set "GEFUNDEN="
for /f "delims=" %%I in ('python -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "GEFUNDEN=%%I"
if not defined GEFUNDEN (
    for /f "delims=" %%I in ('py -3 -c "import sys;print(sys.version.split()[0])" 2^>nul') do set "GEFUNDEN=%%I"
)

if defined GEFUNDEN (
    echo    Gefunden:  Python !GEFUNDEN!  ^(nicht unterstuetzt^)
) else (
    echo    Gefunden:  gar keine Python-Installation
)
echo    Benoetigt: Python 3.10 - 3.12
echo.
echo  Grund: mediapipe ^(das Koerper-Tracking^) wird fuer Python 3.13
echo  und neuer nicht als fertiges Windows-Paket angeboten. Auch die
echo  "Visual C++ Build Tools" helfen hier nicht weiter.
echo.

if defined WINGET_VERSUCHT goto :winget_erfolglos

winget --version >nul 2>&1
if errorlevel 1 goto :kein_winget

set "ANTWORT="
set /p "ANTWORT=Python 3.12 jetzt automatisch installieren? [J/n] "
if /i "!ANTWORT!"=="n"    goto :abbruch
if /i "!ANTWORT!"=="nein" goto :abbruch

echo.
echo  ==^> Installiere Python 3.12 ueber winget
echo      Windows fragt eventuell nach einer Bestaetigung.
echo.
set "WINGET_VERSUCHT=1"
winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
echo.
echo  ==^> Suche erneut nach einem passenden Python
echo.
goto :suche_python

:winget_erfolglos
echo  Die Installation ueber winget hat nicht zum Erfolg gefuehrt.
echo.
goto :manuelle_anleitung

:kein_winget
echo  winget steht auf diesem System nicht zur Verfuegung.
echo.
goto :manuelle_anleitung

:manuelle_anleitung
echo  Bitte Python 3.12 von Hand installieren:
echo      https://www.python.org/downloads/release/python-31210/
echo.
echo  Auf der Seite ganz nach unten scrollen und
echo  "Windows installer (64-bit)" waehlen.
echo.
echo  WICHTIG: Im Installer unten "Add python.exe to PATH" ankreuzen,
echo           sonst wird Python hier nicht gefunden.
echo.
echo  Danach diese Datei einfach erneut doppelklicken.
echo  Ein bereits installiertes neueres Python kann parallel bleiben
echo  und muss nicht entfernt werden.
echo.
pause
exit /b 1

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
echo    - Python-Installation unvollstaendig ^(venv-Modul fehlt^)
echo.
pause
exit /b 1

:pruefung_fehler
echo.
echo  FEHLER: Die Installation lief durch, aber ein Paket laesst sich
echo  nicht laden. Die Meldung oberhalb nennt das betroffene Modul.
echo.
echo  Das deutet auf einen widerspruechlichen Paketstand hin. Am
echo  zuverlaessigsten hilft ein sauberer Neuaufbau:
echo.
echo    1. Den Ordner .venv in diesem Verzeichnis loeschen
echo    2. Diese Datei erneut doppelklicken
echo.
pause
exit /b 1

:install_fehler
echo.
echo  FEHLER: Die Installation der Pakete ist fehlgeschlagen.
echo.
echo  Haeufigste Ursachen, in dieser Reihenfolge pruefen:
echo.
echo   1. Python-Version. Benoetigt wird 3.10 - 3.12.
echo      Verwendet wurde: !PYVER!
echo      Meldet pip "Could not find a version" oder verlangt
echo      "Microsoft Visual C++", ist fast immer die Version schuld.
echo.
echo   2. Internetverbindung unterbrochen.
echo.
echo   3. Beschaedigte Umgebung: den Ordner .venv loeschen und
echo      diese Datei erneut doppelklicken.
echo.
pause
exit /b 1
