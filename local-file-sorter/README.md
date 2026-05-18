# local-file-sorter

> KI-gestützter lokaler File-Sorter – gesteuert über Qwen2.5 7B via Ollama, komplett offline.

---

## Wichtige Einschränkungen (Hard Constraints)

> **ACHTUNG: Dateien werden NIEMALS gelöscht.**
>
> Das System verschiebt Dateien ausschließlich mit `shutil.move`. Löschoperationen (`os.remove`,
> `os.unlink`, `shutil.rmtree`, `send2trash` o.Ä.) sind im gesamten Projekt verboten.
>
> Das LLM darf ausschließlich `move_file` und `create_folder` vorschlagen.
> Jeder Plan mit anderen Operationen wird vollständig abgelehnt.

---

## Beschreibung

`local-file-sorter` scannt ein Verzeichnis, sendet die Dateiliste an ein lokales LLM (Qwen2.5 7B Q4
via Ollama) und lässt dieses einen Sortierplan erstellen. Der Nutzer sieht eine Vorschau aller
geplanten Verschiebeoperationen und muss diese explizit bestätigen, bevor etwas ausgeführt wird.
Jeder Schritt wird als JSON-Lines in einer Logdatei protokolliert.

**Ablauf:** Scan → LLM-Plan → Validierung → Preview → Bestätigung → Log → Ausführung

---

## Voraussetzungen

- Python 3.11 oder neuer
- [Ollama](https://ollama.ai) installiert **und gestartet** (`ollama serve`)
- Modell einmalig herunterladen (ca. 4,5 GB):

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
```

> **Hinweis:** Ollama muss laufen, bevor die Anwendung gestartet wird.
> Das Modell muss einmalig mit `ollama pull qwen2.5:7b-instruct-q4_K_M` heruntergeladen werden.
> Ohne laufendes Ollama und das gepullte Modell ist keine LLM-Funktionalität verfügbar.

- NVIDIA GPU empfohlen (RTX 3060 6 GB VRAM oder besser)

---

## Setup

```bash
# 1. Repository klonen / Projektordner aufrufen
cd local-file-sorter

# 2. Virtuelles Environment anlegen
python -m venv .venv

# 3. Environment aktivieren
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 4. Abhängigkeiten installieren
pip install -r requirements.txt

# 5. Anwendung starten
python main.py
```

---

## Konfiguration

Die Konfiguration befindet sich in `config/settings.yaml`.

Wichtige Einstellungen:

| Schlüssel | Standard | Beschreibung |
|-----------|----------|--------------|
| `ollama.model` | `qwen2.5:7b-instruct-q4_K_M` | Verwendetes Modell |
| `ollama.base_url` | `http://localhost:11434` | Ollama-Server-URL |
| `app.dry_run` | `false` | Trockenlauf – keine echten Datei-Operationen |
| `app.max_files_per_batch` | `100` | Maximale Dateien pro Sortier-Durchlauf |
| `app.language` | `de` | Sprache der Benutzeroberfläche |

---

## Logs

Alle Operationen werden als JSON-Lines in `./logs/` gespeichert:

```json
{"timestamp": "2025-01-15T14:32:00.123456+00:00", "op_type": "move_file", "source": "/pfad/datei.txt", "destination": "/ziel/datei.txt", "status": "success", "error": null}
```
