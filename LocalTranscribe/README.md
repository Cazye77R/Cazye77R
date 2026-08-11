# LocalTranscribe

Lokale, datenschutzkonforme Transkription von Audiodateien mit Sprechererkennung und KI-gestützter Nachbearbeitung – komplett ohne Cloud-Dienste.

## Features

- Transkription via [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (Modell `large-v3`, optimiert für Deutsch)
- Sprecherdiarisierung via [pyannote.audio](https://github.com/pyannote/pyannote-audio)
- LLM-Nachbearbeitung (Zusammenfassung, Protokoll, Maßnahmen, Q&A u. a.) via [Ollama](https://ollama.ai)
- Einfache Web-Oberfläche mit [Streamlit](https://streamlit.io)
- Direkte Audio-Aufnahme im Browser
- Export als `.txt` und `.json`

## Schnellstart (Windows)

Zwei Doppelklicks – mehr ist nicht nötig:

| Datei | Wann | Internet |
|---|---|---|
| `start_online.bat` | Einmalig zum Einrichten und nach Updates | ja |
| `start_offline.bat` | Für den täglichen Gebrauch | **nein** |

`start_online.bat` legt die virtuelle Umgebung an, installiert die Pakete und
lädt genau die benötigten Modelle. Danach startet `start_offline.bat` die App
ohne jeden Netzwerkzugriff auf Modell-Server.

Unter Linux/macOS entsprechend `./start.sh --setup` und `./start.sh`.

Beide rufen nur `launcher.py` auf – dort steckt die gesamte Logik.

## Was das Gerät verlässt

| | `start_online.bat` | `start_offline.bat` |
|---|---|---|
| pip → PyPI | ja (Pakete) | **nein** |
| HuggingFace → Modelle | ja (nur die benötigten) | **nein** (gesperrt) |
| Telemetrie (Streamlit / HuggingFace) | **nein** | **nein** |
| Audio, Transkript, KI-Ergebnis | **nein** | **nein** |
| Erreichbar von anderen Geräten im Netz | **nein** | **nein** |

Audio, Transkripte und Analyseergebnisse verlassen das Gerät in **keinem** Modus.
Whisper und pyannote laufen lokal, Ollama auf `localhost`.

Konkret abgeschaltet:

- **Streamlit-Telemetrie** (`gatherUsageStats`) sowie der E-Mail-Prompt beim ersten Start
- **HuggingFace-Telemetrie**; im Offline-Modus zusätzlich `HF_HUB_OFFLINE`, damit
  nicht bei jedem Modell-Ladevorgang ein Netzwerk-Roundtrip zur Cache-Prüfung stattfindet
- **Netzwerk-Bindung**: Streamlit lauscht nur auf `localhost`, nicht im LAN
- **Externe Bilder** in der KI-Antwort werden vor dem Rendern entfernt, damit der
  Browser sie nicht nachlädt

Nachprüfbar mit:

```bash
python launcher.py --print-env
```

## Voraussetzungen

| Komponente | Version / Hinweis |
|---|---|
| Python | 3.9 oder neuer |
| CUDA | 11.8+ empfohlen (GPU-Beschleunigung), sonst CPU |
| Ollama | Lokal installiert und gestartet (`ollama serve`) |
| HuggingFace-Token | Nur für die Sprechererkennung, nur beim ersten Download |

### HuggingFace-Token

Wird **ausschließlich** benötigt, um das Diarisierungs-Modell einmalig
herunterzuladen. Ohne Token läuft alles außer der Sprechererkennung.

1. Kostenloses Konto anlegen auf [huggingface.co](https://huggingface.co)
2. Bedingungen akzeptieren für [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1) und [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
3. Token erstellen unter **Settings → Access Tokens → New token** (Typ: *Read*)
4. `.env.example` nach `.env` kopieren und `HF_TOKEN` eintragen

## Ollama einrichten

```bash
# Installieren (Linux)
curl -fsSL https://ollama.ai/install.sh | sh

# Modell herunterladen (Beispiel)
ollama pull llama3

# Server starten
ollama serve
```

## Bedienung

1. **Audio hochladen** (`.mp3`, `.wav`, `.m4a`, `.ogg`, `.flac`, `.wma`) oder im Browser aufnehmen
2. **Einstellungen** in der Seitenleiste anpassen (Modell, Sprache, Ausgabeformat)
3. **„Transkribieren"** klicken
4. Transkript mit Zeitstempeln und Sprecherlabels ansehen
5. Ergebnis als `.txt` oder `.json` herunterladen

## Projektstruktur

```
LocalTranscribe/
├── launcher.py           # Start-Logik: venv, Installation, Offline-Riegel
├── start_online.bat      # Einrichten + starten (Windows)
├── start_offline.bat     # Nur starten, ohne Netz (Windows)
├── start.sh              # Beides für Linux/macOS
├── app.py                # Streamlit-Oberfläche
├── transcriber.py        # Whisper-Transkription
├── diarizer.py           # Sprechererkennung
├── llm_processor.py      # Ollama-Integration
├── utils.py              # Zeitstempel, Sprecherfarben, Ausgabe-Filter
├── config.py             # Konfiguration & Konstanten
├── test_workflow.py      # Smoke-Tests (ohne ML-Modelle lauffähig)
├── requirements.txt
├── .env.example          # HF_TOKEN-Vorlage
└── .streamlit/           # Telemetrie aus, nur localhost
```

## Konfiguration

Alle Standardwerte sind in `config.py` zentralisiert:

| Variable | Standardwert | Beschreibung |
|---|---|---|
| `WHISPER_MODEL` | `large-v3` | Whisper-Modellgröße |
| `WHISPER_DEVICE` | automatisch | `cuda` falls verfügbar, sonst `cpu` |
| `WHISPER_COMPUTE_TYPE` | `int8` | Präzision – spart ~50 % VRAM gegenüber `float16` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama-API-Adresse |
| `OLLAMA_GENERATE_TIMEOUT` | `120` | Sekunden bis zum Abbruch einer LLM-Anfrage |
| `SUPPORTED_FORMATS` | `.mp3 .wav .m4a ...` | Erlaubte Dateitypen |

Upload-Grenze und Netzwerk-Bindung stehen in `.streamlit/config.toml`.

## Hinweise

- **VRAM**: Whisper und pyannote passen auf 6 GB nicht gleichzeitig ins VRAM. Die
  Pipeline lädt daher nacheinander und gibt den Speicher jeweils wieder frei.
  Reicht der Speicher trotzdem nicht, weicht Whisper automatisch auf die CPU aus.
- **Modellgrößen**: `large-v3` braucht ca. 3 GB Download und ~2,5 GB VRAM mit
  `int8`. Für schwächere Hardware `medium` oder `small` in der Seitenleiste wählen.
- **Arbeitsspeicher beim Upload**: Eine hochgeladene Datei wird einmal im RAM
  gehalten und einmal in eine temporäre Datei geschrieben – die Spitzenlast
  entspricht etwa der doppelten Dateigröße.
- **Tests**: `python test_workflow.py` läuft ohne installierte ML-Pakete durch;
  die entsprechenden Abschnitte werden dann übersprungen.
