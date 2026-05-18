# local-file-sorter

KI-gestützter, lokaler Datei-Sorter auf Basis von **Qwen2.5 7B Q4** via Ollama.

---

## ⚠ Harte Einschränkungen (immer aktiv, nicht deaktivierbar)

| Regel | Details |
|-------|---------|
| **Kein Löschen** | Das Programm löscht niemals Dateien oder Ordner – auch nicht leere. |
| **Nur `shutil.move`** | Datei-Operationen ausschließlich via `shutil.move`. |
| **LLM-Tool-Set** | Das Modell darf nur `move` und `create_folder` vorschlagen. Jeder andere Op-Typ lehnt den gesamten Plan ab. |
| **Explizite Bestätigung** | Keine Aktion ohne vorherige Nutzer-Bestätigung im Preview-Dialog. |
| **Pfad-Safety** | Alle Ziel- und Quell-Pfade müssen innerhalb des gewählten Wurzel-Ordners liegen. `../`-Tricks werden abgelehnt. |

---

## Überblick

```
Ordner wählen → Befehl eingeben → Plan generieren (LLM) →
Vorschau prüfen → Bestätigen → Dateien verschieben → Undo möglich
```

Das UI ist ein JARVIS-Cockpit-Style HUD mit Animations-Layer (Pillow + tkinter Canvas).

---

## Installation

### Voraussetzungen

- Python **3.11+** (Windows-Installer enthält tkinter)
- NVIDIA GPU mit ≥ 6 GB VRAM empfohlen (RTX 3060 oder besser)
- Git

### Schritte

```bash
git clone <repo-url>
cd local-file-sorter

# Virtuelle Umgebung anlegen
python -m venv .venv

# Aktivieren
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

# Abhängigkeiten installieren
pip install -r requirements.txt
```

---

## Ollama-Setup

### 1. Ollama installieren

→ https://ollama.com/download

Ollama startet nach der Installation automatisch als Hintergrund-Dienst.

### 2. Modell laden

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
```

Download ca. 4,7 GB. Beim ersten Start automatisch auf die GPU geladen.

### 3. Prüfen

```bash
ollama list
# Ausgabe: qwen2.5:7b-instruct-q4_K_M   ...
```

### 4. Vision-Modell (optional)

Für den Vision-Modus (Bilder nach Inhalt sortieren) wird ein separates Multimodal-Modell benötigt.
Empfohlene Modelle für 6 GB VRAM:

| Modell | Download | VRAM | Qualität |
|--------|---------|------|---------|
| `moondream:1.8b` | ca. 1,1 GB | ~1 GB | Gut für Kategorien |
| `qwen2-vl:2b` | ca. 1,5 GB | ~1,5 GB | Besser, aber langsamer |

```bash
# Empfohlen (Standard):
ollama pull moondream:1.8b

# Alternativ (höhere Qualität):
ollama pull qwen2-vl:2b
```

Beide Modelle laufen parallel zum Text-LLM ohne VRAM-Konflikt, da sie jeweils nur kurz
geladen werden. Das Vision-Modell wird in Einstellungen → **Vision-Modell** konfiguriert.

---

## Starten

```bash
python main.py
```

Beim ersten Start erscheint die Boot-Sequenz (ESC oder Klick zum Überspringen).

---

## Verwendung

### Grundlegender Ablauf

1. **Ordner wählen** – Zielverzeichnis über den `📁 Ordner wählen`-Button auswählen
2. **Befehl eingeben** – Freitext, z. B.:
   - `Sortiere nach Dateiendung in Unterordner`
   - `Alle PDFs nach Documents verschieben`
   - `Bilder nach JAHR/MONAT sortieren`
3. **Plan generieren** – `▶ PLAN GENERIEREN` klicken; LLM analysiert die Dateien
4. **Vorschau prüfen** – Alle geplanten Aktionen in der Treeview-Tabelle sehen
5. **Bestätigen** – `✓ Ausführen` klicken; Bestätigungs-Dialog erscheint
6. **Undo** – `↩ Undo letzte Session` macht alle Moves der letzten Session rückgängig

### Gespeicherte Befehle

- **💾 Speichern** – Aktuellen Befehl mit Namen speichern
- **📂 Verwalten** – Befehle umbenennen oder entfernen
- Befehle werden als YAML in `config/commands/` gespeichert

### Dry-Run-Modus

Einstellungen → **Dry-Run** aktivieren:
- Operationen werden simuliert, keine Dateien bewegt
- Gelbes Banner "DRY-RUN AKTIV" erscheint im Hauptfenster
- Log-Einträge erhalten Status `dry_run` (werden bei Undo ignoriert)

### Vision-Modus

Einstellungen → **Vision-Modus aktivieren**:

1. Einstellungen öffnen, `Vision-Modus aktivieren` anhaken, Vision-Modell eintragen
2. Im Dropdown erscheint `🔍 Vision-Modus (Bilder nach Inhalt)` auswählen
3. `▶ PLAN GENERIEREN` klicken

Das Multimodal-Modell analysiert jeden Bild-Dateiinhalt einzeln und vergibt eine
Kategorie-Bezeichnung. Bilder mit gleicher Kategorie landen im selben Unterordner.

- Unterstützte Formate: `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`
- Klassifizierungen werden SHA256-gecacht (`logs/vision_cache.json`) – jedes Bild
  wird nur einmal analysiert, auch über mehrere Sessions hinweg
- Bilder werden **ausschließlich gelesen**, nie verändert oder gelöscht
- Der erzeugte Plan durchläuft dieselbe Validierungspipeline wie ein Text-LLM-Plan

### Einstellungen

| Feld | Beschreibung |
|------|-------------|
| Ollama URL | Standard: `http://localhost:11434` |
| Modell | Standard: `qwen2.5:7b-instruct-q4_K_M` |
| Dry-Run | Simulationsmodus |
| Animationen aktivieren | HUD-Animationen ein/aus |
| Reduzierte Bewegung | Nur Farb-Wechsel, keine Rotation |
| Boot-Sequenz | Intro-Animation beim Start |
| Vision-Modus aktivieren | Aktiviert Bild-Klassifizierung |
| Vision-Modell | Standard: `moondream:1.8b` |

---

## Große Verzeichnisse

Bei mehr Dateien als `max_files_per_batch` (Standard: 100, konfigurierbar in
`config/settings.yaml`) werden automatisch mehrere LLM-Anfragen gestellt.
Im Status erscheint "Verarbeite Chunk 2/5 …". Die Pläne werden zusammengeführt.

---

## Troubleshooting

### Ollama nicht erreichbar

```
✗  Modell nicht erreichbar – läuft Ollama?
```

- Ollama-Dienst prüfen: `ollama list` im Terminal
- Standard-Port: 11434; URL in Einstellungen kontrollieren
- Windows: Ollama tray-Icon in Systemleiste suchen; ggf. neu starten
- Firewall: Port 11434 für `127.0.0.1` freigeben

### Modell antwortet kein JSON

```
⚠  Plan ungültig: LLM-Antwort konnte nach Retry nicht geparst werden
```

- Exaktes Modell verwenden: `qwen2.5:7b-instruct-q4_K_M`
- Modell aktualisieren: `ollama pull qwen2.5:7b-instruct-q4_K_M`
- Bei anderen Modellen ist JSON-Format nicht garantiert

### Plan abgelehnt – ungültige Aktionen

Ein Detail-Dialog zeigt welche Aktion und warum abgelehnt wurde:
- Pfad außerhalb des Zielordners → LLM hat falschen Pfad ausgegeben
- Quelldatei existiert nicht → Datei wurde zwischenzeitlich verschoben
- `../`-Angriff erkannt → Modell-Output manuell prüfen

### GUI startet nicht

```
ModuleNotFoundError: No module named 'tkinter'
```

- **Windows**: Python-Installer mit "tcl/tk and IDLE" Option neu ausführen
- **Ubuntu/Debian**: `sudo apt install python3-tk`
- **macOS**: `brew install python-tk@3.11`

```
ModuleNotFoundError: No module named 'customtkinter'
```

→ `pip install -r requirements.txt` erneut ausführen (venv aktiv?)

### Dateien wurden nicht verschoben

- Dry-Run aktiv? → Gelbes Banner im Hauptfenster prüfen
- Log-Viewer öffnen (`📄 Log-Viewer`) → Status-Spalte prüfen
- Berechtigungen: Schreibrecht auf Zielordner vorhanden?
- Datei gesperrt (Windows)? Andere Programme schließen

### Undo funktioniert nicht

- Undo liest die letzte `logs/sorter_*.jsonl` Datei
- Nur `success`-Einträge werden rückgängig gemacht (`dry_run` nicht)
- Falls Zieldatei bereits verschoben: Konflikt-Meldung im Status

---

## Projektstruktur

```
local-file-sorter/
├── main.py
├── config/
│   ├── settings.yaml
│   └── commands/                  # Gespeicherte Befehle (YAML)
├── logs/                          # JSON-Lines Logs
├── src/
│   ├── core/
│   │   ├── scanner.py             # Verzeichnis-Scanner
│   │   ├── mover.py               # move_file, resolve_conflict, is_safe_destination
│   │   ├── logger.py              # OperationLogger (JSON-Lines)
│   │   └── undo.py                # Session-Undo
│   ├── llm/
│   │   ├── schemas.py             # SortPlan, SortAction, OpType
│   │   ├── prompts.py             # System-Prompt + few-shot Beispiele
│   │   └── ollama_client.py       # OllamaClient + validate_plan
│   ├── commands/
│   │   └── manager.py             # CommandManager
│   └── gui/
│       ├── theme.py
│       ├── app.py
│       ├── preview_dialog.py
│       ├── log_viewer.py
│       ├── commands_dialogs.py
│       └── hud/                   # Animations-Layer
└── tests/
    ├── test_no_delete.py
    ├── test_path_safety.py
    ├── test_name_conflict.py
    ├── test_undo_roundtrip.py
    └── test_plan_validation.py
```

---

## Tech-Stack

| Komponente | Technologie |
|------------|-------------|
| Sprache | Python 3.11+ |
| LLM | Ollama – qwen2.5:7b-instruct-q4_K_M |
| GUI | CustomTkinter 5.2+ |
| Animationen | tkinter Canvas + Pillow |
| Datenvalidierung | Pydantic v2 |
| Konfiguration | PyYAML |
| Terminal | Rich |
