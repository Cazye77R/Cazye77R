# HandCursor

Maussteuerung per Handgesten über die Webcam – kein Maus-Hardware nötig.
MediaPipe erkennt Handlandmarken in Echtzeit; definierte Gesten werden in
Mausbewegungen, Klicks, Scrollen und Drag & Drop übersetzt.

---

## Installation

### Aus dem Quellcode (empfohlen für Entwicklung)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Starten:

```bash
# Reines OpenCV-Fenster (Produktion)
python hand_cursor.py

# Streamlit-App mit Live-Feed, Profilverwaltung und Kalibrierung
streamlit run app.py
```

### Als standalone EXE (Windows)

Lade die fertige `HandCursor.exe` aus dem [Releases-Bereich](../../releases) herunter
und führe sie direkt aus – keine Python-Installation erforderlich.

Selbst bauen:

```bash
pip install pyinstaller
python build.py          # Release-Build (kein Konsolenfenster)
python build.py --debug  # mit Konsolenfenster zur Fehlersuche
```
Die EXE landet unter `dist/HandCursor.exe`.

---

## Gesten-Übersicht

| Geste | Aktion | Erkennung |
|---|---|---|
| Zeigefingerspitze bewegen | Maus bewegen | `lm[8]` x/y-Position |
| Daumen + Zeigefinger Pinch (kurz) | Linksklick | Pinch < `PINCH_THRESHOLD`, < 0,3 s |
| Doppel-Pinch (schnell wiederholt) | Doppelklick | 2× Pinch innerhalb `DOUBLE_CLICK_WINDOW` |
| Daumen + Mittelfinger Pinch | Rechtsklick | `lm[4]` + `lm[12]` < `PINCH_THRESHOLD` |
| Daumen + Zeigefinger Pinch halten | Drag & Drop | Pinch ≥ `DRAG_THRESHOLD_SEC` → `mouseDown` |
| Zeige- + Mittelfinger gestreckt, Rest eingeklappt | Scroll-Modus | `lm[8]`/`lm[12]` y < PIP-Gelenk; Ring/Klein eingeklappt |
| Hand im Scroll-Modus nach oben | Scroll up | y-Delta negativ |
| Hand im Scroll-Modus nach unten | Scroll down | y-Delta positiv |

---

## Streamlit-App

```bash
streamlit run app.py
```

- **Linke Spalte:** Live-Kamerafeed mit Gesten-Overlay, Badge mit aktueller Geste, FPS-Anzeige
- **Rechte Spalte:** Profil-Dropdown (Default / Gaming / Accessibility), Einstellungs-Slider,
  „Steuerung aktiv"-Checkbox (Gesten testen ohne Mausübernahme), Gesten-Log

### Kalibrierungs-Wizard

```bash
streamlit run app.py  # → Seitennavigation: "calibrate"
```

Dreistufiger Assistent:
1. **Pinch-Kalibrierung** – misst die engste Pinch-Distanz (30 Frames) → neuer `PINCH_THRESHOLD`
2. **Mapping-Bereich** – zeichnet live-Rechteck, während Zeigefinger in alle Ecken geführt wird → neue `MAP_X`/`MAP_Y`
3. **Smooth-Faktor** – Slider mit Live-Vorschau (blau = geglättet, grün = roh)

Ergebnisse werden als benanntes Profil gespeichert.

---

## Profile

Profile liegen als JSON in `profiles/`:

| Profil | Anwendungsfall |
|---|---|
| `default` | Allgemeine Nutzung |
| `gaming` | Niedrige Schwellwerte, schnelle Reaktion |
| `accessibility` | Große Toleranzen, träge Bewegung |
| `calibrated` | Automatisch vom Kalibrierungs-Wizard erstellt |

Eigene Profile über die Streamlit-App oder direkt als JSON in `profiles/` anlegen.

---

## Bekannte Einschränkungen

| Einschränkung | Hinweis |
|---|---|
| **Beleuchtung** | Homogenes, diffuses Licht verbessert die Erkennungsrate deutlich. Gegenlicht (Fenster hinter der Hand) führt zu Aussetzern. |
| **Kamera-Distanz** | Optimale Distanz: 40–70 cm. Bei > 80 cm sinkt die Landmark-Präzision, Pinch-Erkennung wird unzuverlässig. |
| **Einfarbiger Hintergrund** | Strukturierter oder bewegter Hintergrund erhöht False-Positive-Rate bei der Handerkennung. |
| **Eine Hand** | Aktuell wird nur eine Hand gleichzeitig verarbeitet (`max_num_hands=1`). |
| **Betriebssysteme** | Getestet auf Windows 10/11 und Ubuntu 22.04. macOS funktioniert grundsätzlich, PyAutoGUI benötigt dort Accessibility-Rechte. |
| **Webcam-Framerate** | Bei < 20 FPS werden Gesten träger erkannt. USB-Webcam mit 30 FPS empfohlen. |
| **EXE-Startzeit** | Die PyInstaller-EXE entpackt MediaPipe-Modelle beim ersten Start (~5–10 s). Folgestarts sind schneller. |

---

## Screenshots

> *Platzhalter – Screenshots folgen nach erster stabiler Version.*

| Ansicht | |
|---|---|
| OpenCV-Fenster mit Landmark-Overlay | `docs/screenshots/opencv_window.png` |
| Streamlit-App Hauptansicht | `docs/screenshots/streamlit_main.png` |
| Kalibrierungs-Wizard Schritt 2 | `docs/screenshots/calibration_step2.png` |

---

## Projektstruktur

```
hand_cursor.py       Einstiegspunkt (OpenCV-Loop)
gestures.py          GestureDetector-Klasse
config.py            Alle konfigurierbaren Werte
profile_manager.py   Profil laden/speichern/auflisten
app.py               Streamlit-App
pages/calibrate.py   Kalibrierungs-Wizard (Streamlit-Page)
profiles/            Gespeicherte Profile (JSON)
build.py             PyInstaller-Build-Script
version.py           Versionsnummer und App-Name
tests/               Unit-Tests (pytest)
```
