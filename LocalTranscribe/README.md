# LocalTranscribe

Lokale, datenschutzkonforme Transkription von Audiodateien mit Sprechererkennung und KI-gestützter Nachbearbeitung – komplett ohne Cloud-Dienste.

## Features

- Transkription via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Modell `large-v3`, optimiert für Deutsch)
- Sprecherdiarisierung via [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- LLM-Nachbearbeitung (Zusammenfassung, Aktionspunkte, Q&A) via [Ollama](https://ollama.ai)
- Einfache Web-Oberfläche mit [Streamlit](https://streamlit.io)
- Export als `.txt` und `.json`

## Voraussetzungen

| Komponente | Version / Hinweis |
|---|---|
| Python | 3.10 oder neuer |
| CUDA | 11.8+ empfohlen (GPU-Beschleunigung) |
| Ollama | Lokal installiert und gestartet (`ollama serve`) |
| HuggingFace-Token | Für pyannote-Modell-Download erforderlich |

### HuggingFace-Token erhalten

1. Kostenloses Konto anlegen auf [huggingface.co](https://huggingface.co)
2. Token erstellen unter: **Settings → Access Tokens → New token** (Typ: *Read*)
3. Den Modellen [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) und [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0) auf HuggingFace zustimmen

## Installation

```bash
# 1. Repository klonen
git clone <repo-url>
cd LocalTranscribe

# 2. Virtuelle Umgebung erstellen
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Abhängigkeiten installieren
pip install -r requirements.txt

# 4. Umgebungsvariablen konfigurieren
cp .env.example .env
# .env öffnen und HF_TOKEN eintragen
```

## Ollama einrichten

```bash
# Ollama installieren (Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# Modell herunterladen (Beispiel: llama3)
ollama pull llama3

# Ollama-Server starten (läuft im Hintergrund)
ollama serve
```

## Kurzanleitung

```bash
# App starten
streamlit run app.py
```

Im Browser öffnet sich automatisch `http://localhost:8501`.

1. **Audiodatei hochladen** – unterstützte Formate: `.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.wma`
2. **Einstellungen** in der Seitenleiste anpassen (Modell, Sprache, Ollama-Modell)
3. **"Transkribieren"** klicken und auf das Ergebnis warten
4. Transkript mit Zeitstempeln und Sprecherlabels ansehen
5. **Zusammenfassung / Aktionspunkte** vom LLM generieren lassen
6. Ergebnis als `.txt` oder `.json` herunterladen

## Projektstruktur

```
LocalTranscribe/
├── app.py              # Streamlit-Oberfläche
├── transcriber.py      # Whisper-Transkription
├── diarizer.py         # Sprechererkennung
├── llm_processor.py    # Ollama-Integration
├── config.py           # Konfiguration & Konstanten
├── requirements.txt
├── .env.example        # HF_TOKEN-Vorlage
└── outputs/            # Exportierte Transkripte
```

## Konfiguration

Alle Standardwerte sind in `config.py` zentralisiert:

| Variable | Standardwert | Beschreibung |
|---|---|---|
| `WHISPER_MODEL` | `large-v3` | Whisper-Modellgröße |
| `WHISPER_DEVICE` | `cuda` | `cuda` oder `cpu` |
| `WHISPER_COMPUTE_TYPE` | `float16` | Präzision (`float16`, `int8`) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama-API-Adresse |
| `SUPPORTED_FORMATS` | `.mp3 .wav .m4a ...` | Erlaubte Dateitypen |
| `OUTPUT_DIR` | `outputs` | Zielordner für Exporte |

## Hinweise

- Auf reiner CPU-Nutzung `WHISPER_DEVICE = "cpu"` und `WHISPER_COMPUTE_TYPE = "int8"` setzen.
- Das Modell `large-v3` benötigt ca. 10 GB VRAM; für weniger VRAM `medium` oder `small` wählen.
- Die erste Ausführung lädt die Modellgewichte herunter (~3 GB für `large-v3`).
