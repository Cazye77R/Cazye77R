# MAINFRAME

Personal app launcher with user management. Runs programs and websites in a protected area via browser. Local server for home network (Linux + Windows).

## Tech Stack

- **Frontend:** React (Vite) + Tailwind CSS + Framer Motion + Zustand + React Router
- **Backend:** FastAPI + SQLModel + SQLite + bcrypt + psutil + GitPython

## Development

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` and proxies `/auth/*` to the backend.

## Design System: "Dark Terminal"

| Token | Value |
|---|---|
| Background | `#0D1117` |
| Surface | `#161B22` |
| Border | `#30363D` |
| Cyan (primary) | `#58A6FF` |
| Green (success) | `#3FB950` |
| Red (error) | `#F85149` |
| Orange (warning) | `#D29922` |
| Text | `#E6EDF3` |
| Text muted | `#8B949E` |
| Heading font | JetBrains Mono |
| Body font | IBM Plex Mono |

Glow effect: `box-shadow: 0 0 10px rgba(88,166,255,0.3)`

## Project Structure

```
mainframe/
├── backend/
│   ├── main.py          FastAPI app + CORS
│   ├── database.py      SQLModel engine + session
│   ├── models.py        User, Session DB models
│   ├── auth.py          Auth routes (login, logout, me, setup)
│   └── config.py        Session timeout, secret key
├── frontend/
│   ├── index.html
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx              Router setup + ProtectedRoute
│   │   ├── index.css            Tailwind + global styles
│   │   ├── stores/
│   │   │   └── authStore.js     Zustand auth store (persisted)
│   │   ├── pages/
│   │   │   ├── BootSequence.jsx Typing boot animation → login/setup
│   │   │   ├── Login.jsx        Terminal-style login form
│   │   │   ├── Setup.jsx        First-run admin account wizard
│   │   │   └── Dashboard.jsx    Protected dashboard (placeholder)
│   │   └── components/
│   │       ├── TerminalText.jsx Typing animation component
│   │       ├── GlowButton.jsx   Cyan-glow button
│   │       ├── TerminalInput.jsx Monospace input with cyan focus
│   │       └── Toast.jsx        Toast notifications + imperative API
└── CLAUDE.md
```

## Auth Flow

1. App opens → `/` (BootSequence) runs typing animation
2. Checks `GET /auth/setup-required` → redirects to `/setup` or `/login`
3. Setup creates first admin via `POST /auth/setup`
4. Login authenticates via `POST /auth/login` → receives bearer token
5. Token stored in localStorage via Zustand persist
6. Protected routes check token; invalid/expired tokens redirect to `/login`
