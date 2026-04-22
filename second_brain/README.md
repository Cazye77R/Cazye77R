# SecondBrain Agent

Lokales KI-gestütztes Wissensmanagement-System auf Basis von Streamlit, ChromaDB und Ollama.

## Schnellstart

```bash
python launcher.py
```

Der Launcher prüft automatisch alle Abhängigkeiten, startet die App und öffnet den Browser.

## Voraussetzungen

- Python 3.10+
- [Ollama](https://ollama.ai) installiert und gestartet
- Empfohlene Modelle:
  - `ollama pull llama3`
  - `ollama pull nomic-embed-text`

## Projektstruktur

```
second_brain/
├── core/           # Konfiguration, DB-Zugriff, Kernlogik
├── ai/             # Ollama-Integration, Embeddings, RAG
├── plugins/        # Erweiterbare Plugin-Schnittstellen
├── ui/
│   ├── pages/      # Streamlit-Seiten (Multipage)
│   └── components/ # Wiederverwendbare UI-Komponenten
├── data/
│   ├── vault/      # Markdown-Notizen (Obsidian-kompatibel)
│   └── chroma_db/  # Vektordatenbank
├── assets/         # Bilder, Icons, statische Dateien
├── bootstrap.py    # Abhängigkeitsprüfung & -installation
└── launcher.py     # Einstiegspunkt (EXE-fähig)
```

## Konfiguration

Alle Pfade und Modell-Einstellungen in `core/config.py` anpassen.

| Variable | Standard |
|---|---|
| `CHAT_MODEL` | `llama3` |
| `EMBED_MODEL` | `nomic-embed-text` |
| `OLLAMA_URL` | `http://localhost:11434` |
| `VERSION` | `1.0.0` |
