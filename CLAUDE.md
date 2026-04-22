# HandCursor

## Projektname
HandCursor

## Stack
- Python 3.10+
- MediaPipe
- OpenCV
- PyAutoGUI
- NumPy

## Hauptdatei
`hand_cursor.py`

## Ziel
Maussteuerung per Handgesten über Webcam. Das Programm erfasst die Webcam-Eingabe in Echtzeit, erkennt Handlandmarken via MediaPipe und übersetzt definierte Gesten in Mausbewegungen und -aktionen.

## Projektstruktur
```
hand_cursor.py   # Einstiegspunkt, Webcam-Loop, Koordinatenverarbeitung
gestures.py      # Gestenlogik und -erkennung
config.py        # Konfigurationsparameter (Empfindlichkeit, Auflösung, etc.)
tests/           # Tests
requirements.txt # Abhängigkeiten
```

## Hinweise
- Keine Streamlit-Integration in dieser Phase
- Ausgabe ausschließlich über reines OpenCV-Fenster
- Gestenlogik ist strikt von der Hauptdatei getrennt (gestures.py)
- Konfiguration zentral in config.py verwaltet
