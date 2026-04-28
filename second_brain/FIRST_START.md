# SecondBrain Agent – Erste Schritte

## Voraussetzungen

### Python (nur für Quell-Installation)
- Python **3.10 oder neuer**: https://www.python.org/downloads/
- Beim Windows-Installer unbedingt **"Add Python to PATH"** ankreuzen

### Ollama (für KI-Funktionen)
1. Ollama installieren: **https://ollama.ai**
2. Nach der Installation im Terminal ausführen:
   ```
   ollama pull llama3
   ollama pull nomic-embed-text
   ```
3. Ollama läuft dann automatisch im Hintergrund (Systemtray)

> **Ohne Ollama** funktionieren Notiz-Verwaltung, Suche und Graph weiterhin.
> Nur KI-Funktionen (Chat, Briefing, Tag-Vorschläge) sind eingeschränkt.

---

## Installation & Start

### Option A – EXE (empfohlen für Windows)
1. `SecondBrain.exe` doppelklicken
2. App öffnet sich automatisch im Browser

### Option B – Python-Quellcode

**Erstinstallation** (einmalig):
```
install.bat
```

**App starten:**
```
python launcher.py
```

---

## Erster Start

1. Die App öffnet sich im Browser unter **http://localhost:8501**
2. Navigiere zu **⚙️ Einstellungen**
3. Vault-Pfad prüfen / anpassen (Standard: `data/vault/`)
4. **"Vault neu indizieren"** klicken
5. Fertig – alle drei Beispiel-Notizen sind jetzt verfügbar 🧠

---

## Übersicht der Funktionen

| Seite | Funktion |
|---|---|
| 📊 Dashboard | Statistiken, Tag-Cloud, Tages-Briefing |
| 📝 Notizen | Lesen, Schreiben, KI-Tag-Vorschläge |
| 🔍 Suche | Semantisch, Volltext, Hybrid, Tag-Filter |
| 💬 Chat | Fragen an deinen Vault stellen |
| 🕸️ Graph | Verbindungen zwischen Notizen visualisieren |
| ⚙️ Einstellungen | Ollama, Backup, Reindex |

---

## Häufige Probleme

**"Ollama nicht gefunden"**
→ Starte Ollama (Systemtray-Icon oder `ollama serve` im Terminal)

**Browser öffnet sich nicht**
→ Manuell aufrufen: http://localhost:8501

**Port 8501 belegt**
→ Im Terminal: `launcher.py` anpassen auf einen freien Port

**"Import Error" beim Start**
→ `install.bat` erneut ausführen oder `pip install -r requirements.txt`

---

## Vault-Struktur

Alle Notizen werden als Markdown-Dateien gespeichert:

```
data/
└── vault/
    ├── Meine_Notiz.md
    ├── Python_Grundlagen.md
    └── ...
```

Du kannst Notizen auch direkt mit jedem Texteditor bearbeiten –
der eingebaute Datei-Watcher erkennt Änderungen automatisch.

---

*SecondBrain Agent v1.0.0 · Lokal · Privat · Open Source*
