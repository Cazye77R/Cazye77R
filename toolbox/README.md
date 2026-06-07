# Toolbox

Ein internes Web-Tool auf Basis von **FastAPI** (Backend) und **React + Vite** (Frontend).

---

## Setup

### Backend

```bash
cd toolbox
pip install -r requirements.txt
```

### Frontend

```bash
cd toolbox/frontend
npm install
```

---

## Entwicklung

Backend und Frontend separat starten:

**Terminal 1 — Backend** (aus `toolbox/`):
```bash
python -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 — Frontend** (aus `toolbox/frontend/`):
```bash
npm run dev
```

Frontend läuft auf http://localhost:5173 und nutzt das Backend auf http://localhost:8000.

### Standard-Login

| Feld     | Wert    |
|----------|---------|
| Username | `admin` |
| Passwort | `admin` |

---

## Produktion

### Windows

```bat
start.bat
```

### Linux / Mac

```bash
chmod +x start.sh
./start.sh
```

Das Skript baut das Frontend (falls `frontend/dist` fehlt) und startet den Server auf http://localhost:8000.

---

## API-Dokumentation

Erreichbar unter http://localhost:8000/docs (Swagger UI).

---

## Datenbank

SQLite unter `data/toolbox.db` — wird beim ersten Start automatisch erstellt. Für PostgreSQL/Supabase die `DATABASE_URL` in `backend/config.py` anpassen.
