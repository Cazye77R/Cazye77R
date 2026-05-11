# RadarScope – CLAUDE.md

## Projektübersicht
Python-Anwendung zum Lesen und Visualisieren von LD2450-Radarframes über serielle Schnittstelle.

## Entwicklungsregeln

- **Max 50 Zeilen pro Commit** – kleine, atomare Änderungen
- **Jeden Schritt einzeln testen** bevor der nächste beginnt
- **`py` statt `python`** für alle Kommandozeilenaufrufe
- **Windows** ist die Zielplattform (COM-Ports, `py`-Launcher)

## Befehle

```bat
py run.py --port COM3          # Frames empfangen und als Hex ausgeben
py -m pytest tests/            # Tests ausführen
py -m streamlit run radarscope/ui/dashboard.py  # Dashboard starten
```

## Architektur

| Modul | Zweck |
|---|---|
| `serial_reader.py` | Rohdaten vom seriellen Port lesen, Frame-Sync |
| `frame_parser.py` | LD2450-Frame in strukturierte Daten parsen |
| `tracker.py` | Ziel-Tracking über mehrere Frames |
| `ui/dashboard.py` | Streamlit-Dashboard zur Visualisierung |

## LD2450 Frame-Format

- Header: `AA FF 03 00`
- Footer: `55 CC`
- Baudrate: 256000, 8N1
