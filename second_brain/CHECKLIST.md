# SecondBrain Agent – Abschluss-Test-Checkliste

Führe diese Tests nach jedem Release durch, um sicherzustellen,
dass alle Kernfunktionen wie erwartet funktionieren.

---

## 0. Voraussetzungen

- [ ] Python 3.10+ installiert (`python --version`)
- [ ] Ollama läuft (`ollama serve` / Systemtray-Icon)
- [ ] Modelle vorhanden (`ollama list` zeigt `llama3` und `nomic-embed-text`)
- [ ] Abhängigkeiten installiert (`pip install -r requirements.txt`)

---

## 1. Start

- [ ] **Neues Projekt starten:**
  ```
  python launcher.py
  ```
  - Erwartung: Keine Fehler in der Konsole, Browser öffnet http://localhost:8501
  - Erwartung: Ollama-Status in der Seitenleiste zeigt 🟢

- [ ] **Onboarding:** Bei leerem Vault erscheint der Onboarding-Screen (3 Schritte + Button)

---

## 2. Notizen erstellen

- [ ] **5 Notizen erstellen** mit ➕ Neue Notiz:
  - `KI Grundlagen` mit Tags `ki, python` und Inhalt mit `[[Machine Learning]]`
  - `Machine Learning` mit Tags `ki, ml` und Inhalt mit `[[Python Basics]]`
  - `Python Basics` mit Tags `python` und 3× `TODO: Beispielcode`
  - `Produktivität` mit Tags `produktivität, workflow`
  - `Wochenbericht 2024` mit Tags `work, review`

- [ ] Jede Notiz zeigt nach dem Speichern einen Toast `✅ Erstellt`
- [ ] Notizen erscheinen in der linken Liste, sortierbar nach Datum/Name/Wörtern

---

## 3. Notiz anzeigen und bearbeiten

- [ ] `KI Grundlagen` öffnen → Wikilink `→ Machine Learning` erscheint unten
- [ ] `Machine Learning` öffnen → Backlink `← KI Grundlagen` ist sichtbar
- [ ] Bearbeiten-Modus aktivieren → Keyboard-Shortcut-Hinweis sichtbar
- [ ] Inhalt ändern → `⚠️ Ungespeicherte Änderungen` erscheint
- [ ] Speichern → Toast `💾 Gespeichert!`
- [ ] Notiz löschen → Bestätigung erscheint → Toast `🗑️ Gelöscht`

---

## 4. Semantische Suche

- [ ] Seite **Suche** öffnen
- [ ] Modus: `Semantisch`, Query: `maschinelles lernen`
  - Erwartung: `Machine Learning` und `KI Grundlagen` erscheinen mit grünen Badges (≥ 0.7)
- [ ] Modus: `Volltext`, Query: `TODO`
  - Erwartung: `Python Basics` erscheint (enthält 3× TODO)
- [ ] Modus: `Hybrid`, Query: `python programmierung`
  - Erwartung: Ergebnisse aus beiden Modi kombiniert
- [ ] Tag-Filter: `python` wählen → Ergebnisse nur aus python-getaggten Notizen
- [ ] **ChromaDB-Fallback:** Wenn Ollama offline → automatisch Volltext, kein Absturz

---

## 5. Chat

- [ ] Seite **Chat** öffnen
- [ ] Frage eingeben: `Was steht in meinen Notizen über Machine Learning?`
  - Erwartung: Streaming-Antwort erscheint, Quellen `[[Machine Learning]]` werden angezeigt
- [ ] Auf Quelle klicken → navigiert zur Notiz
- [ ] `Chat leeren` → Verlauf wird zurückgesetzt
- [ ] `Als Notiz` speichern → neue Notiz `Chat YYYY-MM-DD HH:MM` im Vault

---

## 6. Wissensgraph

- [ ] Seite **Graph** öffnen
- [ ] Graph zeigt alle 5 Notizen als Knoten
- [ ] Kante zwischen `KI Grundlagen` → `Machine Learning` sichtbar
- [ ] Slider `Min. Verbindungen = 1` → isolierte Knoten verschwinden
- [ ] Tag hervorheben: `python` → python-Notizen leuchten pink auf
- [ ] Orphan-Toggle aus → isolierte Knoten ausgeblendet
- [ ] Knoten in Sidebar suchen → Details werden angezeigt
- [ ] **Cache-Test:** Einstellungen nicht ändern, Seite neu laden → kein Spinner (aus Cache)

---

## 7. KI-Aktionen (Notiz-Panel)

- [ ] Notiz `Python Basics` öffnen
- [ ] `Tags analysieren` klicken → Vorschläge erscheinen (z.B. `tutorial`, `anfänger`)
- [ ] `Links suchen` klicken → Ähnliche Notizen mit Confidence-Bar erscheinen
- [ ] `Struktur vorschlagen` → Strukturierter Vorschlag im Expander sichtbar
- [ ] `✅ Übernehmen` → Notizinhalt wird durch Vorschlag ersetzt

---

## 8. Tages-Briefing

- [ ] Dashboard öffnen
- [ ] `📋 Tages-Briefing generieren` klicken
- [ ] Spinner erscheint → nach Abschluss: Briefing-Text sichtbar
- [ ] Datei `data/briefings/YYYY-MM-DD.md` wurde erstellt

---

## 9. Einstellungen

- [ ] Vault-Pfad prüfen → `✅ Verzeichnis gefunden – N Markdown-Dateien`
- [ ] Vault-Pfad speichern → Toast erscheint
- [ ] Ollama-Verbindung testen → Erfolg oder klare Fehlermeldung
- [ ] `Vault neu indizieren` → Fortschrittsbalken von 10% → 100% → Toast
- [ ] Backup erstellen → ZIP-Download-Button erscheint
- [ ] DB zurücksetzen → Bestätigung erforderlich → danach Metriken bei 0

---

## 10. Fehlerszenarien

- [ ] **Ollama offline:** Banner `⚠️ Ollama nicht verfügbar` erscheint auf Dashboard und Notizen
- [ ] **Leerer Vault:** Onboarding-Screen statt Dashboard
- [ ] **Nicht gefundene Notiz:** Warnung statt Absturz
- [ ] **ChromaDB-Fehler:** Suche fällt auf Volltext zurück, Meldung erscheint

---

## 11. EXE-Build (Windows)

- [ ] `build_exe.bat` ausführen
  - Erwartung: `dist/SecondBrain.exe` wird erstellt
  - Größe: 100–300 MB (je nach Abhängigkeiten)

- [ ] EXE auf **frischem Verzeichnis** testen:
  - Neuen Ordner ohne Python-Umgebung wählen
  - `SecondBrain.exe` dort hineinkopieren und starten
  - Erwartung: App startet, Browser öffnet sich, Vault ist leer (Onboarding)

---

## 12. Test-Suite

```bash
cd second_brain
pytest test_core.py test_database.py test_ai.py test_agents.py -v
```

- [ ] 191 Tests, 0 Fehler

---

## Status-Legende

| Symbol | Bedeutung |
|---|---|
| [ ] | Nicht getestet |
| [x] | Bestanden |
| [!] | Fehlgeschlagen – Issue erstellen |

---

*Checkliste zu SecondBrain Agent v1.0.0*
