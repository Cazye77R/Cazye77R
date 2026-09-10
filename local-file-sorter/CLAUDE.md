# local-file-sorter – Projektdokumentation für Claude

## Projektziel

Lokaler, KI-gestützter File-Sorter für Windows. Das System scannt ein vom Nutzer gewähltes Verzeichnis,
lässt ein lokales LLM (Qwen2.5 7B Q4 via Ollama) einen Sortierplan erstellen, zeigt dem Nutzer eine
Vorschau und führt die Operationen erst nach expliziter Bestätigung aus. Alle Schritte werden als
JSON-Lines in einer Logdatei festgehalten.

---

## HARTE REGELN – NIEMALS VERLETZEN

### Lösch-Verbot (absolut)

**Jegliche Lösch-Operation ist strikt VERBOTEN.**

Folgende Funktionen/Methoden dürfen im gesamten Projekt NIEMALS importiert oder aufgerufen werden:

- `os.remove`
- `os.unlink`
- `Path.unlink`
- `shutil.rmtree`
- `shutil.rmdir`
- `send2trash` (darf nicht installiert oder importiert werden)
- Jegliche andere Funktion, die eine Datei oder ein Verzeichnis löscht, in den Papierkorb verschiebt
  oder unwiederbringlich entfernt

**Dateien werden AUSSCHLIESSLICH mit `shutil.move(source, destination)` bewegt.**

---

## LLM-Tool-Set

Das Modell darf in seinem Sortierplan **ausschließlich** folgende zwei Operationen vorschlagen:

| Tool | Signatur | Beschreibung |
|------|----------|--------------|
| `move_file` | `move_file(source: str, destination: str)` | Verschiebt eine Datei |
| `create_folder` | `create_folder(path: str)` | Legt ein Verzeichnis an |

Schlägt das Modell **irgendeine andere Operation** vor (umbenennen, löschen, kopieren, ausführen, …),
muss der **komplette Plan abgelehnt** und dem Nutzer ein Fehler gemeldet werden. Es darf keine
Teilausführung stattfinden.

---

## Pflicht-Reihenfolge (Pipeline)

Jede Sortier-Session MUSS in dieser exakten Reihenfolge ablaufen:

```
1. Scan        – Verzeichnis einlesen, Dateiliste + Metadaten sammeln
2. LLM-Plan    – Dateiliste an Qwen2.5 senden, strukturierten Plan empfangen
3. Validierung – Plan auf erlaubte Operationen prüfen (nur move_file / create_folder)
4. Preview     – Vorschau im UI anzeigen (welche Datei → wohin)
5. User-Confirm – Explizite Bestätigung durch den Nutzer abwarten (kein Auto-Execute)
6. Log         – Geplante Operationen als JSON-Lines vormerken (status: "pending")
7. Execute     – Operationen ausführen, Log-Einträge auf "success" oder "error" aktualisieren
```

**Keine Stufe darf übersprungen werden.**

---

## Logging-Format

Jede Operation wird als ein JSON-Lines-Eintrag (eine Zeile pro Operation) in `./logs/` geschrieben.

Pflichtfelder:

```json
{
  "timestamp": "2025-01-15T14:32:00.123456+00:00",
  "op_type": "move_file",
  "source": "/pfad/zur/datei.txt",
  "destination": "/ziel/pfad/datei.txt",
  "status": "success",
  "error": null
}
```

- `op_type`: `"move_file"` oder `"create_folder"`
- `status`: `"pending"` | `"success"` | `"error"`
- `error`: `null` bei Erfolg, Fehlermeldung als String bei Fehler

---

## Tech-Stack

| Komponente | Technologie |
|------------|-------------|
| Sprache | Python 3.11+ |
| LLM-Backend | Ollama (lokal) |
| LLM-Modell | `qwen2.5:7b-instruct-q4_K_M` |
| GUI | CustomTkinter |
| Bildverarbeitung | Pillow |
| Datenvalidierung | Pydantic v2 |
| Konfiguration | PyYAML |
| Terminal-Output | Rich |

---

## Hardware-Ziel

- GPU: NVIDIA RTX 3060 mit 6 GB VRAM
- Betriebssystem: Windows 10/11
- Das Modell `qwen2.5:7b-instruct-q4_K_M` muss vollständig in den 6 GB VRAM passen

---

## Projektstruktur

```
local-file-sorter/
├── CLAUDE.md                  # Diese Datei
├── README.md
├── requirements.txt
├── main.py                    # Einstiegspunkt
├── config/
│   ├── settings.yaml          # Konfiguration
│   └── commands/              # Gespeicherte Sortier-Commands
├── logs/                      # JSON-Lines Logdateien
├── src/
│   ├── __init__.py
│   ├── core/                  # Scanner, Pipeline, Validator
│   │   └── __init__.py
│   ├── llm/                   # Ollama-Client, Prompt-Builder
│   │   └── __init__.py
│   ├── commands/              # Command-Definitionen
│   │   └── __init__.py
│   └── gui/                   # CustomTkinter UI
│       └── __init__.py
├── scripts/                   # Hilfsskripte
└── tests/                     # Unit- und Integrationstests
```

---

## Entwicklungshinweise für Claude

- **Niemals** Löschoperationen vorschlagen oder implementieren – auch nicht als "Aufräumen"
- Bei Unklarheiten über Datei-Operationen: immer nachfragen, nie raten
- Pydantic-Modelle für alle LLM-Antworten verwenden (strukturierte Ausgabe)
- `dry_run: true` in settings.yaml aktivieren für Tests ohne echte Datei-Bewegungen
- Alle Pfade als `pathlib.Path`-Objekte handhaben, nie als rohe Strings
