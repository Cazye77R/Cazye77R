# HandCursor

Maussteuerung per Handgesten über die Webcam – keine Maus-Hardware nötig.
MediaPipe erkennt Handlandmarken in Echtzeit; definierte Gesten werden in
Mausbewegungen, Klicks, Scrollen und Drag & Drop übersetzt.

---

## Schnellstart

Ein Skript genügt – es legt beim ersten Aufruf eine virtuelle Umgebung an,
installiert die Abhängigkeiten und startet dann:

```bash
# Linux / macOS
./start.sh              # interaktives Menü
./start.sh ui           # Streamlit-Oberfläche
./start.sh app          # reines OpenCV-Fenster
./start.sh calibrate    # Kalibrierungs-Wizard
```

```bat
REM Windows (oder start.bat doppelklicken)
start.bat
start.bat ui
```

Ohne die Wrapper geht es genauso: `python run.py ui`.

| Modus | Wirkung |
|---|---|
| `ui` | Streamlit-Oberfläche mit Live-Bild, Profilen und Einstellungen |
| `app` | Reines OpenCV-Fenster (die schlanke Variante) |
| `calibrate` | Kalibrierungs-Wizard |
| `test` | Testsuite |
| `build` | Standalone-EXE bauen |
| `doctor` | Installation prüfen – erster Anlaufpunkt bei Problemen |

Nützliche Flags: `--profile NAME`, `--camera N`, `--port N`, `--no-venv`,
`--reinstall`, `--force`.

**Wenn etwas nicht startet:** `python run.py doctor` prüft Python-Version,
Anzeige, Kameras, alle Abhängigkeiten und die Profile – und nennt zu jedem
fehlenden Paket den passenden Installationsbefehl.

---

## Installation

### Aus dem Quellcode

Der Launcher erledigt das normalerweise. Von Hand:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # nur für Tests und Build
```

Python **3.10 – 3.12** (MediaPipe veröffentlicht oberhalb von 3.12 noch keine
Wheels; der Launcher prüft das und sagt es deutlich).

### Als standalone EXE (Windows)

```bash
python run.py build          # oder: python build.py
python build.py --debug      # mit Konsolenfenster zur Fehlersuche
```
Die EXE landet unter `dist/HandCursor.exe`.

---

## Gesten-Übersicht

| Geste | Aktion | Erkennung |
|---|---|---|
| Zeigefingerspitze bewegen | Maus bewegen | `lm[8]` x/y-Position |
| Daumen + Zeigefinger Pinch (kurz) | Linksklick | Pinch < `pinch_threshold`, kürzer als `drag_threshold` |
| Doppel-Pinch (schnell wiederholt) | Doppelklick | 2× Pinch innerhalb `double_click_window` |
| Daumen + Mittelfinger Pinch | Rechtsklick | `lm[4]` + `lm[12]`, Flanke – feuert einmal pro Geste |
| Daumen + Zeigefinger Pinch halten | Drag & Drop | Pinch ≥ `drag_threshold` → `mouseDown` |
| Zeige- + Mittelfinger gestreckt, Rest eingeklappt | Scroll-Modus | Fingerspitze über PIP-Gelenk |
| Im Scroll-Modus Hand nach oben / unten | Scroll up / down | y-Delta zwischen zwei Frames |

**Notaus:** Die Maus schnell in eine Bildschirmecke reißen bricht die Steuerung
ab (PyAutoGUI-Failsafe). Abschaltbar mit `--no-failsafe`. Im OpenCV-Fenster
beendet zusätzlich `q` oder `Esc`.

Zum gefahrlosen Ausprobieren: `--no-control` bzw. die Checkbox
„Steuerung aktiv" in der Oberfläche – Gesten werden erkannt und angezeigt,
die Maus bleibt unberührt.

---

## Oberfläche

```bash
./start.sh ui
```

- **Links:** Live-Kamerabild mit Gesten-Overlay, farbiges Badge der aktuellen
  Geste, FPS-Anzeige
- **Rechts:** Profil-Auswahl, Einstellungs-Regler, „Steuerung aktiv",
  „Kamera freigeben", Gesten-Log der letzten 10 Gesten

Kamera und Kalibrierungs-Seite teilen sich einen einzigen Kamera-Thread, der
Seitenwechsel übernimmt das Gerät sauber – ohne Standbild und ohne Neustart.

### Kalibrierungs-Wizard

1. **Pinch** – misst über 30 Frames die engste Pinch-Distanz → `pinch_threshold`
2. **Mapping** – Zeigefinger in alle Ecken führen, das grüne Rechteck zeigt den
   erfassten Bereich → `map_x` / `map_y`
3. **Smooth** – Regler mit Live-Vorschau (blau = geglättet, grün = roh)

Das Ergebnis wird als Profil gespeichert, sofort aktiviert und gilt auch für
`./start.sh app`.

---

## Profile

Profile sind JSON-Dateien in `profiles/`:

| Profil | Anwendungsfall |
|---|---|
| `default` | Allgemeine Nutzung |
| `gaming` | Niedrige Schwellwerte, schnelle Reaktion |
| `accessibility` | Große Toleranzen, träge Bewegung |
| `calibrated` | Wird vom Kalibrierungs-Wizard angelegt |

```bash
python hand_cursor.py --list-profiles
python hand_cursor.py --profile gaming
```

Das zuletzt aktivierte Profil wird gemerkt und beim nächsten Start verwendet.
In der EXE liegen die mitgelieferten Profile schreibgeschützt im Bundle;
eigene Profile landen im Benutzerverzeichnis und überleben einen Neustart.
`HANDCURSOR_HOME` verlegt dieses Verzeichnis.

---

## Bekannte Einschränkungen

| Einschränkung | Hinweis |
|---|---|
| **Beleuchtung** | Homogenes, diffuses Licht verbessert die Erkennung deutlich. Gegenlicht (Fenster hinter der Hand) führt zu Aussetzern. |
| **Kamera-Distanz** | Optimal 40–70 cm. Ab etwa 80 cm sinkt die Landmark-Präzision, die Pinch-Erkennung wird unzuverlässig. |
| **Hintergrund** | Strukturierter oder bewegter Hintergrund erhöht die Fehlerkennungsrate. |
| **Eine Hand** | Es wird nur eine Hand gleichzeitig ausgewertet (`max_num_hands=1`). |
| **Eine Kamera-Instanz** | Alle Seiten teilen sich eine Kamera. Andere Programme (Videokonferenz) müssen sie freigeben. |
| **Betriebssysteme** | Windows 10/11 und Ubuntu 22.04. macOS läuft grundsätzlich, PyAutoGUI braucht dort Bedienungshilfen-Rechte. |
| **Kein Headless-Betrieb** | Die App steuert die echte Maus und braucht einen Desktop. Über SSH ohne X11-Weiterleitung bricht der Launcher mit einer Erklärung ab. |
| **EXE-Startzeit** | Die EXE entpackt die MediaPipe-Modelle beim ersten Start (~5–10 s). |

---

## Screenshots

> *Platzhalter – folgen nach der ersten stabilen Version.*

| Ansicht | |
|---|---|
| OpenCV-Fenster mit Landmark-Overlay | `docs/screenshots/opencv_window.png` |
| Streamlit-App Hauptansicht | `docs/screenshots/streamlit_main.png` |
| Kalibrierungs-Wizard Schritt 2 | `docs/screenshots/calibration_step2.png` |

---

## Projektstruktur

```
run.py               Launcher (Setup + Start) – stdlib only
start.sh / start.bat Wrapper für Linux/macOS bzw. Windows
hand_cursor.py       Einstiegspunkt OpenCV-Fenster (mit CLI)
app.py               Streamlit-Oberfläche
pages/calibrate.py   Kalibrierungs-Wizard
gestures.py          GestureDetector – gesamte Gesten- und Flankenerkennung
camera.py            Prozessweiter Einzelbesitzer der Kamera
runtime.py           Live-Einstellungen, von allen Seiten geteilt
config.py            Standardwerte + SETTING_KEYS
profile_manager.py   Profile laden/speichern/auflisten
profiles/            Profile (JSON)
build.py             PyInstaller-Build
version.py           Version und App-Name
tests/               Testsuite (pytest)
```

`stock_model/` im selben Repository ist ein davon unabhängiges Projekt
(LSTM-Kursprognose) mit eigenen Abhängigkeiten in `requirements-stock.txt`.

---

## Tests

```bash
python run.py test        # oder: python -m pytest tests/ -v
```

Die Testsuite läuft ohne Kamera und ohne Display – `tests/` importiert
bewusst keine Module, die `cv2` oder `pyautogui` auf Modulebene laden.
