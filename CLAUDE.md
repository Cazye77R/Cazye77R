# HandCursor

## Projektname
HandCursor

## Stack
- Python 3.10–3.12 (MediaPipe hat oberhalb von 3.12 keine Wheels)
- MediaPipe, OpenCV, PyAutoGUI, NumPy
- Streamlit für die Oberfläche und den Kalibrierungs-Wizard

## Ziel
Maussteuerung per Handgesten über Webcam. Die Webcam-Eingabe wird in Echtzeit
erfasst, MediaPipe erkennt Handlandmarken, definierte Gesten werden in
Mausbewegungen, Klicks, Scrollen und Drag & Drop übersetzt.

## Starten
Immer über den Launcher – er legt die venv an, installiert und startet:
```
./start.sh ui           # Streamlit-Oberfläche
./start.sh app          # reines OpenCV-Fenster
./start.sh calibrate    # Kalibrierungs-Wizard
./start.sh test         # Testsuite
./start.sh doctor       # Diagnose
```
`start.bat` unter Windows, `python run.py <modus>` überall.

## Projektstruktur
```
run.py               Launcher (Setup + Start), stdlib only
start.sh / start.bat Plattform-Wrapper
hand_cursor.py       Einstiegspunkt OpenCV-Fenster, argparse-CLI
app.py               Streamlit-Oberfläche
pages/calibrate.py   Kalibrierungs-Wizard (Streamlit-Page)
gestures.py          GestureDetector: Gesten- UND Flankenerkennung
camera.py            Prozessweiter Einzelbesitzer der Kamera
runtime.py           Live-Einstellungen, von allen Seiten geteilt
config.py            Standardwerte + SETTING_KEYS/SETTING_ATTRS
profile_manager.py   Profile laden/speichern/auflisten
profiles/            Profile (JSON)
build.py             PyInstaller-Build
version.py           VERSION, APP_NAME
tests/               pytest
```

## Architektur-Regeln

**Eine Kamera, ein Besitzer.** `camera.py` hält den einzigen `VideoCapture`
und die einzige MediaPipe-Instanz des Prozesses. Seiten rufen
`camera.acquire(owner, processor)`; der letzte Aufrufer gewinnt. Niemals
irgendwo sonst `cv2.VideoCapture` öffnen (Ausnahme: `hand_cursor.py`, das ein
eigener Prozess ist und `camera.open_capture()` benutzt).

**Processors laufen im Worker-Thread.** Sie dürfen nur einfache Dicts und
Queues anfassen und niemals `st.*` aufrufen.

**Einstellungen leben in `runtime.py`, nicht in `config.py`.** `config.py`
enthält ausschließlich Defaults und wird zur Laufzeit nicht beschrieben.
Neue Einstellung? Nur in `config.SETTING_ATTRS` eintragen – Profile, UI und
GestureDetector leiten sich davon ab.

**Flankenerkennung gehört in den GestureDetector.** Aufrufer dispatchen nur.
`hand_cursor.py` und `app.py` müssen sich identisch verhalten – jede
Verhaltensänderung gehört in `gestures.py`, nicht in einen der Aufrufer.

**`get_click_action()` wird jeden Frame aufgerufen**, auch ohne erkannte Hand.
Wird das ausgelassen, bleibt ein Klick unbegrenzt in der Warteschlange und
feuert später an völlig falscher Stelle.

**`update(None)` bei fehlender Hand** ist Pflicht: Nur so wird ein laufender
Drag beendet, sonst bleibt die Maustaste gedrückt.

## Testbarkeit (wichtig)
`tests/` darf **niemals** `app.py`, `hand_cursor.py` oder ein Modul
importieren, das `cv2`/`pyautogui`/`mediapipe` auf Modulebene lädt – die
Testsuite muss ohne Display und ohne Kamera laufen. `camera.py` importiert
`cv2` deshalb bewusst erst innerhalb der Funktionen.

## Hinweise
- `stock_model/` ist ein unabhängiges Projekt im selben Repository
  (LSTM-Kursprognose), Abhängigkeiten in `requirements-stock.txt`.
  Nicht mit HandCursor vermischen.
- `pyautogui.FAILSAFE` ist standardmäßig **an** (Notaus über Bildschirmecke).
