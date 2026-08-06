# Stock Return Forecasting Model

Dieses Repository enthält ein einfaches, trainingsfähiges KI-Modell, das auf historischen Aktienkursbewegungen basiert. Es nutzt ein LSTM, um aus vergangenen Renditefenstern die nächste Rendite abzuleiten und kann auf beliebige Kurs-CSV-Dateien angewendet werden.

## Funktionsumfang
- CSV-Einlesung und Bereinigung (Sortierung nach Datum, Prozentänderungen, optionale Normalisierung).
- Erzeugung von Sequenz-Datensätzen beliebiger Fensterlänge.
- LSTM-Modell mit LayerNorm, Dropout und frei konfigurierbarer Hidden-Size/Layer-Anzahl.
- Trainings-Skript mit Train/Val-Split, Loss-Reporting und Speicherung der Gewichte.

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Datenerwartung
Eine CSV-Datei mit mindestens zwei Spalten:
- `date`: Zeitstempel oder Datum (wird per `pandas` geparst)
- `close`: Schlusskurs oder Preiswert

Die Reihenfolge der Zeilen ist egal, das Skript sortiert automatisch nach Datum.

## Training starten
```bash
python -m stock_model.train path/zum/daten.csv \
  --window 60 \
  --batch-size 128 \
  --epochs 30 \
  --lr 5e-4 \
  --hidden-size 256 \
  --layers 2 \
  --dropout 0.2 \
  --train-ratio 0.85 \
  --output artifacts
```
Standardwerte sind im Skript hinterlegt, sodass Sie optional nur den CSV-Pfad angeben müssen.

## Forecast-Oberfläche im Dark Mode
Starte die moderne Web-Oberfläche, um Daten hochzuladen, ein Modell zu laden oder kurzfristig zu trainieren und sofort einen Forecast zu erzeugen:

```bash
streamlit run stock_model/app.py
```

Die App bietet:
- Dark-Theme mit Plotly-Visualisierungen.
- Upload von CSV-Daten sowie optional eines `.pt`-Checkpoints.
- Wahl der Fenstergröße, Forecast-Horizont und Schnelltraining mit wenigen Epochen.
- Anzeige der prognostizierten Renditen und fortgeschriebenen Preise.

---

# Live-Kamera-Erkennung & Körper-Tracking

Zweite, eigenständige Anwendung in diesem Repository (`camera_detection/`): erkennt live
über die Kamera, was sich vor der Linse befindet — mit Rahmen, Beschriftung und
vollständigem Körper-Skeleton.

## Voraussetzung: Python 3.9 – 3.12

> **Python 3.13 und 3.14 funktionieren nicht.** Für sie gibt es kein fertiges
> `mediapipe`-Paket (das Körper-Tracking), weder für Windows noch für Linux/macOS.
> pip versucht dann einen Build aus dem Quelltext und bricht mit einer irreführenden
> Meldung ab — unter Windows mit *„Microsoft Visual C++ 14.0 or greater is required"*.
> **Die C++ Build Tools zu installieren hilft dabei nicht**, mediapipe lässt sich so
> nicht bauen. Stattdessen
> [Python 3.12](https://www.python.org/downloads/release/python-31210/) verwenden.

Ein bereits installiertes neueres Python kann parallel bestehen bleiben — die Starter
suchen sich gezielt eine passende Version.

## Starten

**Windows:** Doppelklick auf `Kamera-Erkennung.bat`.

Der Starter sucht automatisch nach einem passenden Python (3.12 → 3.11 → 3.10 → 3.9).
Findet er keins, bietet er die Installation von Python 3.12 per `winget` an oder zeigt
die Anleitung zum manuellen Download.

Beim ersten Start fragt er, ob die benötigten Pakete installiert werden sollen
(ca. 2–3 GB). Sie landen isoliert im Unterordner `.venv`, die System-Python-Installation
bleibt unberührt. Danach startet die App und der Browser öffnet sich automatisch.

**macOS / Linux:**
```bash
./start.sh --setup   # einmalig: Abhängigkeiten installieren
./start.sh           # danach nur noch das
```

Steht die passende Version nicht als Standard-`python3` bereit, gezielt auswählen:
```bash
PYTHON=python3.12 ./start.sh --setup
```

**Manuell:**
```bash
python -m streamlit run camera_detection/app.py
```

## Funktionen

- **Drei Erkennungsmodi:** nur Objekte, nur Personen, oder beides gleichzeitig.
- **Objekterkennung** über YOLOv8 mit allen 80 COCO-Klassen.
- **Körper-Tracking** über MediaPipe Pose mit 33 Landmarken pro Person.
- **Klassenfilter:** gezielt einzelne Klassen auswählen (z. B. nur `car` und `dog`).
- **Umschaltbare Anzeige:** Rahmen, Beschriftung und Skeleton einzeln ein-/ausblendbar.
- **Modellwahl:** YOLOv8n (schnell), YOLOv8s (ausgewogen), YOLOv8m (genau).
- **Kamera-Auflösung** und Konfidenzschwelle einstellbar.
- **Live-Statistik:** FPS, erkannte Personen und Objekte, verworfene Frames.

Die Gewichte des gewählten Modells werden beim ersten Verwenden automatisch geladen.

## Hinweis zu OpenCV

`cv2` wird bewusst nicht in `requirements.txt` gepinnt — es kommt transitiv über
`ultralytics` und `mediapipe`. Auf Headless-Servern anschließend zusätzlich
`opencv-contrib-python-headless` installieren; Details stehen als Kommentar in
`requirements.txt`.

---

## Ergebnisse
Nach dem Training wird ein Checkpoint unter `artifacts/return_lstm.pt` gespeichert, der sowohl die Modellgewichte als auch die wichtigsten Hyperparameter (inkl. Normalisierungs-Statistiken) enthält. Dieses Format kann mit PyTorch geladen und für Inferenz oder weiteres Feintuning verwendet werden.

Viel Erfolg beim Experimentieren mit Ihren Kursdaten!
