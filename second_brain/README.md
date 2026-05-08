# 🧠 SecondBrain Agent

> Ein vollständig lokales, KI-gestütztes Wissensmanagementsystem –  
> deine Notizen, deine KI, kein Cloud-Zwang.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-red)
![License](https://img.shields.io/badge/License-MIT-green)
![Ollama](https://img.shields.io/badge/Ollama-lokal-orange)

---

## ✨ Features

| Feature | Beschreibung |
|---|---|
| 📝 **Notiz-Editor** | Markdown-Editor mit Vorschau, Wikilinks `[[Note]]`, Tags, Backlinks |
| 🔍 **Intelligente Suche** | Semantisch (Embeddings), Volltext, Hybrid, Tag-Suche mit Score-Badges |
| 💬 **KI-Chat** | RAG-gestützter Chat über deine Notizen mit Quellen-Zitaten |
| 🕸️ **Wissensgraph** | Interaktiver pyvis-Graph aller Notiz-Verbindungen |
| 📊 **Dashboard** | Statistiken, Tag-Cloud, Tages-Briefing, Verbindungsvorschläge |
| 🤖 **KI-Aktionen** | Tag-Vorschläge, Link-Vorschläge, Notiz-Strukturierung |
| 📋 **Tages-Briefing** | Automatisch generierter Tagesbericht über deinen Vault |
| ⚙️ **Einstellungen** | Vault-Pfad, Ollama-Verbindung, Reindex, Backup, DB-Reset |
| 💾 **Auto-Persistenz** | SQLite + ChromaDB, Live-Sync per Datei-Watcher |
| 🔒 **100% Lokal** | Keine Cloud, keine API-Keys, alle Daten bleiben bei dir |

---

## 📸 Screenshots

```
┌─────────────────────────────────────────────────────────────────┐
│  🧠 SecondBrain Agent              [Sidebar]                     │
│  ─────────────────────────────────────────────────────────────  │
│  🏠 Startseite      │  📊 Vault: 42 Notizen · 18.500 Wörter     │
│  📊 Dashboard       │  ─────────────────────────────────────    │
│  📝 Notizen         │  🕐 Zuletzt bearbeitet                     │
│  🔍 Suche           │  ┌──────────────────────────────────────┐  │
│  💬 Chat            │  │ 📄 Python Basics          [ki, python]│  │
│  🕸️  Graph          │  │ Grundlegende Python-Konzepte...       │  │
│  ⚙️  Einstellungen  │  └──────────────────────────────────────┘  │
│  ─────────────────  │                                            │
│  📊 Notizen:  42    │  🏷️ Tag-Cloud                             │
│  📊 Wörter: 18.5k   │        python    ki                        │
│  🏷️ Tags:    15    │     ml    workflow    notizen               │
│  🔗 Links:   28     │  ─────────────────────────────────────    │
│  ─────────────────  │  📋 Tages-Briefing                         │
│  🟢 Ollama verbunden│  Heute: 3 neue Notizen, 2 Verbindungen...  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation

### Option 1 – Windows EXE (empfohlen)

1. `SecondBrain.exe` aus dem Release herunterladen  
   *oder* selbst bauen: `build_exe.bat` doppelklicken
2. EXE doppelklicken – App startet automatisch im Browser

### Option 2 – pip (plattformübergreifend)

```bash
# Python 3.10+ vorausgesetzt
git clone https://github.com/dein-user/second_brain
cd second_brain
pip install -r requirements.txt
python launcher.py
```

### Option 3 – conda

```bash
conda create -n secondbrain python=3.11
conda activate secondbrain
pip install -r requirements.txt
python launcher.py
```

Danach öffnet sich der Browser automatisch auf `http://localhost:8501`.

---

## 🤖 Ollama-Setup

Ollama stellt alle KI-Modelle lokal bereit (kein Cloud-Zwang).

```bash
# 1. Ollama installieren
#    → https://ollama.ai  (Windows / macOS / Linux, kostenlos)

# 2. Ollama starten (läuft dann als Hintergrunddienst)
ollama serve

# 3. Modelle laden  (einmalig ~5 GB Download)
ollama pull llama3               # Chat-Modell (~4.7 GB)
ollama pull nomic-embed-text     # Embedding-Modell (~274 MB)
```

> **Ohne Ollama** funktionieren Notiz-Verwaltung, Graph und  
> Volltext-Suche normal. Semantische Suche, Chat und KI-Aktionen  
> werden automatisch deaktiviert und zeigen einen Hinweis-Banner.

### Alternative Modelle

| Zweck | Empfohlen | Leichter (weniger RAM) | Leistungsstärker |
|---|---|---|---|
| Chat | `llama3` (8 GB) | `phi3:mini` (2 GB) | `mixtral` (48 GB) |
| Embeddings | `nomic-embed-text` | `all-minilm` | `mxbai-embed-large` |

Modell in `core/config.py` ändern:
```python
CHAT_MODEL  = "phi3:mini"         # für schwächere Hardware
EMBED_MODEL = "nomic-embed-text"  # bleibt meist optimal
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Aktion |
|---|---|
| `Ctrl+Enter` | Formular / Texteingabe bestätigen |
| `Tab` / `Shift+Tab` | Zwischen UI-Elementen navigieren |
| `Esc` | Dialog / Expander schließen |

> Der Notiz-Editor zeigt einen **Speicher-Hinweis** direkt über dem  
> Textfeld. Beim Verlassen des Edit-Modus mit ungespeicherten  
> Änderungen erscheint eine gelbe Warnung.

---

## 📁 Projektstruktur

```
second_brain/
├── launcher.py              # Einstiegspunkt (EXE + Python)
├── bootstrap.py             # Abhängigkeits-Check & Auto-Install
├── requirements.txt         # Python-Abhängigkeiten
├── second_brain.spec        # PyInstaller Spec (EXE-Build)
├── build_exe.bat            # Windows EXE Build-Skript
├── install.bat              # Erstinstallation (Python-Quelle)
├── FIRST_START.md           # Schnellstart-Anleitung
├── CHECKLIST.md             # Abschluss-Test-Checkliste
│
├── core/
│   ├── config.py            # Pfade, DB-Engine, Modell-Konstanten
│   ├── config_store.py      # data/config.json (Nutzereinstellungen)
│   ├── markdown_parser.py   # Frontmatter, Wikilinks, Tags, render
│   ├── vault_manager.py     # CRUD für Markdown-Notizen
│   ├── database.py          # SQLAlchemy ORM (Notes, Tags, Links)
│   ├── file_watcher.py      # Watchdog Live-Sync mit Debounce
│   └── graph_engine.py      # NetworkX DiGraph + pyvis Export
│
├── ai/
│   ├── ollama_client.py     # HTTP-Client für Ollama API
│   ├── embedder.py          # ChromaDB-Embeddings, Batch-Größe 50
│   ├── rag_engine.py        # Semantische/Hybrid-Suche + Antworten
│   ├── note_assistant.py    # Tag/Link-Vorschläge, Strukturierung
│   └── briefing_agent.py    # Tages-Briefing Generator
│
├── plugins/
│   ├── smart_search.py      # 4 Suchmodi + Highlighting
│   └── link_suggester.py    # TTL-gecachte Verbindungsvorschläge
│
├── ui/
│   ├── streamlit_app.py     # Hauptseite + globales CSS (Dark Theme)
│   ├── app_state.py         # @cache_resource, @cache_data, Session
│   ├── components/
│   │   ├── note_card.py     # Karten-HTML-Komponenten
│   │   └── graph_view.py    # pyvis Konfiguration + Farblegende
│   └── pages/
│       ├── 01_Dashboard.py  # Statistiken + Briefing + Tag-Cloud
│       ├── 02_Notes.py      # Editor + Viewer + KI-Panel
│       ├── 03_Search.py     # Multi-Modus Suche
│       ├── 04_Chat.py       # RAG-Chat mit Streaming
│       ├── 05_Graph.py      # Wissensgraph (Session-Cache)
│       └── 06_Settings.py   # Konfiguration + Verwaltung
│
└── data/                    # Wird automatisch erstellt
    ├── vault/               # Deine Markdown-Notizen
    ├── chroma_db/           # Vektordatenbank (ChromaDB)
    ├── second_brain.db      # SQLite-Datenbank
    ├── briefings/           # Tages-Briefings (YYYY-MM-DD.md)
    └── config.json          # Nutzereinstellungen (Vault-Pfad, …)
```

---

## 🔌 Plugin-Entwicklung

Neue Funktionen als Plugin in `plugins/` hinzufügen.

### Minimales Plugin

```python
# plugins/my_plugin.py
from __future__ import annotations

class MyPlugin:
    def __init__(self) -> None:
        pass  # Schwere Ressourcen hier initialisieren

    def process(self, note: dict) -> str:
        return f"Ergebnis für: {note['title']}"
```

### Registrierung in `ui/app_state.py`

```python
@st.cache_resource(show_spinner=False)
def get_my_plugin():
    try:
        from plugins.my_plugin import MyPlugin
        return MyPlugin()
    except Exception:
        return None   # Graceful degradation
```

### Verwendung in einer Seite

```python
from ui.app_state import get_my_plugin

plugin = get_my_plugin()
if plugin:
    st.markdown(plugin.process(note))
else:
    st.caption("Plugin nicht verfügbar.")
```

### Konventionen

- Fallback-Verhalten bei fehlender Ollama-Verbindung implementieren
- Schwere Initialisierung im `__init__` (wird nur einmal durch `@cache_resource` ausgeführt)
- Methoden werfen keine Exceptions nach oben – immer `try/except`
- TTL-Caches für wiederholte teure Berechnungen verwenden

---

## 🏗️ Architektur

```
┌──────────────────────────────────────────────────────┐
│                   Streamlit UI                        │
│   Pages: Dashboard · Notes · Search · Chat · Graph   │
└───────────────────┬──────────────────────────────────┘
                    │ app_state.py (@cache_resource/data)
        ┌───────────┼───────────────┐
        ▼           ▼               ▼
  VaultManager   RAGEngine     NoteAssistant
  (Markdown IO)  (Suche+LLM)   (KI-Aktionen)
        │           │               │
        ▼           ▼               │
   SQLAlchemy   ChromaDB ◄──────────┘
   (SQLite DB)  (Vektoren)   NoteEmbedder
        │
        ▼
   FileWatcher ──► VaultManager (Live-Sync)
   (Watchdog)

   OllamaClient ──► Alle AI-Komponenten
   (HTTP, lokal)    (Fallback bei Offline)
```

**Cache-Schichten:**
1. `@st.cache_resource` – Singleton-Objekte (VaultManager, RAGEngine)
2. `@st.cache_data(ttl=300)` – Stats und Tags (5 min TTL)
3. `@st.cache_data(ttl=60)` – Ollama-Status (1 min TTL)
4. `st.session_state` – Graph-HTML (invalidiert bei Vault-Änderungen)

---

## ❓ FAQ

**Warum lokal statt Cloud?**  
Deine Notizen sind privat. Kein API-Key, keine Nutzungsdaten, keine Abhängigkeit von Drittanbietern. Alles läuft auf deiner Hardware – auch offline.

**Welche Modelle werden empfohlen?**  
`llama3` (8B) für Chat – gute Balance aus Qualität und Geschwindigkeit. `nomic-embed-text` für Embeddings – schnell und hochwertig. Für schwächere Hardware: `phi3:mini` (benötigt nur ~2 GB RAM).

**Wie viel RAM brauche ich?**

| Konfiguration | RAM |
|---|---|
| Ohne KI (nur Notizen/Graph) | ~200 MB |
| Mit `phi3:mini` | ~2–3 GB |
| Mit `llama3` (8B, empfohlen) | ~8–10 GB |
| Mit `mixtral` (8x7B) | ~48 GB |

**Kann ich andere Markdown-Editoren verwenden?**  
Ja! Der Datei-Watcher erkennt externe Änderungen automatisch (1 s Debounce). Obsidian, Typora, VS Code, Zettlr – alle kompatibel.

**Wie groß wird die Datenbank?**  
ChromaDB: ~1–5 MB pro 100 Notizen. SQLite: ~0.5 MB pro 100 Notizen.  
Für 1.000 Notizen: ~50 MB gesamt.

**Obsidian-Vault importieren?**  
Direkt kompatibel. Vault-Ordner in `data/vault/` kopieren (oder Pfad in Einstellungen ändern), dann `Vault neu indizieren` klicken.

**Funktioniert SecondBrain offline?**  
Ja, vollständig nach dem einmaligen Ollama-Download (~5 GB).

**Port 8501 ist belegt?**  
`launcher.py` öffnen und `--server.port=8501` auf einen freien Port ändern.

---

## 🛠️ Entwicklung & Tests

```bash
# Alle Tests ausführen
cd second_brain
pytest test_core.py test_database.py test_ai.py test_agents.py -v
# Erwartet: 191 Tests, 0 Fehler

# Streamlit ohne Launcher starten
streamlit run ui/streamlit_app.py

# EXE bauen (Windows)
build_exe.bat
```

---

## 📄 Lizenz

MIT License – freie Nutzung, Änderung und Weitergabe.

---

*SecondBrain Agent v1.0.0 · Gebaut mit Streamlit, Ollama, ChromaDB, NetworkX und ❤️*
