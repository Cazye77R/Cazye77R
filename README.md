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

## Ergebnisse
Nach dem Training wird ein Checkpoint unter `artifacts/return_lstm.pt` gespeichert, der sowohl die Modellgewichte als auch die wichtigsten Hyperparameter enthält. Dieses Format kann mit PyTorch geladen und für Inferenz oder weiteres Feintuning verwendet werden.

Viel Erfolg beim Experimentieren mit Ihren Kursdaten!
