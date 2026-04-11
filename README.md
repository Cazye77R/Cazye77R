# Cazye77R – Tools & Utilities

Dieses Repository enthält zwei unabhängige Python-Tools.

---

## 1. Änderungsmitteilungs-Generator

Erzeugt bis zu 5000 realistische deutsche Änderungsmitteilungen (wie aus einem Konstruktionsbüro) als Textdateien – z. B. für Testdaten, KI-Training oder Demonstrationszwecke.

### Themen
| Kürzel | Thema |
|--------|-------|
| KF | Konstruktionsfehler |
| KW | Kundenwunsch |
| NA | Normänderung |
| FF | Fertigungsfehler |
| MA | Materialaustausch |
| SR | Sicherheitsanforderung |

### Verwendung
```bash
# 5000 Dateien erzeugen
python generate_aenderungen.py --count 5000 --output-dir ./aenderungen

# Reproduzierbar mit festem Seed
python generate_aenderungen.py --count 100 --seed 42

# Nur bestimmte Themen
python generate_aenderungen.py --count 200 --topics Kundenwunsch Fertigungsfehler

# Alle Optionen
python generate_aenderungen.py --help
```

### Optionen
| Parameter | Standard | Beschreibung |
|-----------|----------|--------------|
| `--count` | 100 | Anzahl Dateien (max. 9999) |
| `--output-dir` | `./aenderungen` | Zielverzeichnis |
| `--seed` | zufällig | Seed für Reproduzierbarkeit |
| `--topics` | alle | Themenfilter (Leerzeichen-getrennt) |
| `--prefix` | `aenderung` | Dateinamens-Präfix |
| `--start-index` | 1 | Startnummer der Dateien |

### Ausgabe
Jede Datei enthält:
- **Header**: Dok-Nr., Datum, Bearbeiter, Abteilung, Priorität, Status
- **Bauteil-Abschnitt**: Sachnr., Zeichnungsnr., Revision, Baugruppe
- **Beschreibung**, **Begründung**, **Maßnahmen** (variiert nach Detailstufe)
- Optional: **Betroffene Dokumente**, **Terminplanung**, **Freigabevermerk**

Detailstufen: `kurz` (~1,7 kB) / `mittel` (~2,5 kB) / `lang` (~3,1 kB) — zufällig verteilt (30/40/30 %).

Keine zusätzlichen Abhängigkeiten – nur Python-Stdlib.

---

## 2. Stock Return Forecasting Model

Trainingsfähiges KI-Modell auf Basis historischer Aktienkursbewegungen. Nutzt ein LSTM, um aus vergangenen Renditefenstern die nächste Rendite vorherzusagen.

### Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Datenformat
CSV-Datei mit mindestens zwei Spalten:
- `date`: Datum (wird automatisch geparst und sortiert)
- `close`: Schlusskurs

### Training
```bash
python -m stock_model.train path/zu/daten.csv \
  --window 60 --batch-size 128 --epochs 30 \
  --hidden-size 256 --layers 2 --dropout 0.2 \
  --output artifacts
```

### Web-Oberfläche (Dark Mode)
```bash
streamlit run stock_model/app.py
```

Bietet: CSV-Upload, Checkpoint-Laden, Schnelltraining, Forecast-Visualisierung.

### Ergebnis
Checkpoint wird unter `artifacts/return_lstm.pt` gespeichert (Modellgewichte + Hyperparameter).
