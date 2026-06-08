# CLAUDE.md — Toolbox Projekt-Dokumentation

> Diese Datei wird von Claude Code automatisch gepflegt.
> Zuletzt aktualisiert: 2026-06-08

## Projekt-Überblick
- Name: Toolbox (Branding konfigurierbar: Hofblick/Koppel/Hufspur/Stallgeflüster)
- Zweck: Lokale Multi-User Tool-Plattform für tiergestützte Pädagogik
- Stack: FastAPI + SQLite (SQLAlchemy) | React (Vite) + Tailwind CSS v4
- Betrieb: Lokal via start.bat / start.sh, später Cloud-fähig (Cloudflare Pages + Supabase)

## Ordnerstruktur
```
toolbox/
├── CLAUDE.md
├── backend/
│   ├── main.py             ← FastAPI App, CORS, StaticFiles Mount, Lifespan
│   ├── config.py           ← DATABASE_URL, SECRET_KEY, Token-Expiry
│   ├── database.py         ← SQLAlchemy Engine + SessionLocal
│   ├── auth.py             ← JWT + Password Hashing + get_current_user/admin
│   ├── models.py           ← User, AppSettings, Tier, Eintrag, eintrag_tiere
│   └── routers/
│       ├── users.py        ← Auth (login/register) + User CRUD + Passwort ändern
│       ├── settings.py     ← Branding GET (public) / PUT (admin)
│       └── reittagebuch.py ← Tiere, Einträge, Stats, Export (.xlsx), Backup
├── frontend/
│   ├── src/
│   │   ├── App.jsx         ← Router, BrandingProvider, StartupAnimation
│   │   ├── context/        ← AuthContext, BrandingContext, ToastContext
│   │   ├── lib/api.js      ← apiFetch wrapper, alle API-Calls
│   │   ├── components/     ← Layout, ProtectedRoute, AdminRoute, StartupAnimation,
│   │   │                      ErrorBoundary, OfflineBanner, Skeleton, Spinner
│   │   └── pages/
│   │       ├── Login.jsx
│   │       ├── Dashboard.jsx          ← Tool-Grid + Letzte-Aktivität-Widget
│   │       ├── admin/
│   │       │   ├── UserManagement.jsx
│   │       │   └── BrandingSettings.jsx ← Theme-Auswahl + Vorschau + Speichern
│   │       └── reittagebuch/
│   │           ├── ReittagebuchLayout.jsx ← Sub-Tabs
│   │           ├── EntryForm.jsx     ← Neuer/Edit Eintrag
│   │           ├── Overview.jsx      ← Tabelle (Desktop) + Cards (Mobile)
│   │           ├── Stats.jsx         ← Recharts BarChart + LineChart
│   │           ├── Animals.jsx       ← Tier-Grid + Modal
│   │           └── ExportPage.jsx    ← Excel-Download + DB-Backup (Admin)
│   ├── index.html
│   └── package.json
├── data/                   ← SQLite DB (gitignored)
├── start.bat / start.sh    ← Production: venv + build-check + uvicorn
├── dev.bat / dev.sh        ← Entwicklung: Backend (--reload) + Frontend parallel
└── requirements.txt
```

## Datenbank-Schema

### users
| Spalte | Typ | Bemerkung |
|--------|-----|-----------|
| id | INTEGER PK | |
| username | VARCHAR UNIQUE | Login-Name |
| email | VARCHAR NULLABLE | |
| hashed_password | VARCHAR | bcrypt |
| display_name | VARCHAR | |
| is_admin | BOOLEAN | Default: False |
| is_active | BOOLEAN | Default: True |
| created_at | DATETIME | |

### app_settings
| Spalte | Typ | Bemerkung |
|--------|-----|-----------|
| id | INTEGER PK | |
| key | VARCHAR UNIQUE | z.B. "branding" |
| value | TEXT | JSON-String |
| updated_at | DATETIME | |
| updated_by | INTEGER FK | → users.id |

### tiere
| Spalte | Typ | Bemerkung |
|--------|-----|-----------|
| id | INTEGER PK | |
| name | VARCHAR | z.B. "Pollie" |
| typ | VARCHAR | "Pferd"/"Esel"/"Pony"/"Maultier" |
| emoji | VARCHAR | Default: "🐴" |
| aktiv | BOOLEAN | Soft-delete |
| user_id | INTEGER FK | → users.id |
| created_at | DATETIME | |

### eintraege
| Spalte | Typ | Bemerkung |
|--------|-----|-----------|
| id | INTEGER PK | |
| datum | DATE | |
| aktivitaet | TEXT | |
| besonderheiten | TEXT NULL | |
| anpassungen | TEXT NULL | |
| anzahl_kinder | INTEGER | Default: 0 |
| anzahl_jugendliche | INTEGER | Default: 0 |
| user_id | INTEGER FK | → users.id |
| created_at / updated_at | DATETIME | |

### eintrag_tiere (Many-to-Many, kein eigenes Model)
| eintrag_id FK → eintraege.id | tier_id FK → tiere.id |

## API-Routen

### Auth & Users (`/api/auth/`, `/api/users/`)
- `POST /api/auth/login` → Token + UserOut
- `POST /api/auth/register` → Nur wenn DB leer (Bootstrap)
- `GET /api/users/me` → Aktueller User
- `PUT /api/users/me/password` → Passwort ändern (old + new)
- `GET /api/users/` → Alle User (Admin)
- `POST /api/users/` → User anlegen (Admin)
- `PUT /api/users/{id}` → User bearbeiten (Admin)
- `DELETE /api/users/{id}` → User löschen (Admin, nicht sich selbst)

### Settings (`/api/settings/`)
- `GET /api/settings/branding` → Branding-Config (public, kein Auth)
- `PUT /api/settings/branding` → Branding updaten (Admin)

### Reittagebuch (`/api/reittagebuch/`)
- `GET/POST /tiere` | `PUT/DELETE /tiere/{id}` (DELETE = soft-delete)
- `GET /eintraege?von=&bis=&tier_id=&limit=&offset=` → gefiltert
- `GET /eintraege/{id}` | `POST /eintraege` | `PUT /eintraege/{id}` | `DELETE /eintraege/{id}`
- `GET /stats?von=&bis=` → gesamt_einheiten, wochen_durchschnitt, tiere_einsaetze, wochen_verlauf
- `GET /export?von=&bis=` → .xlsx Download (StreamingResponse, openpyxl)
- `GET /backup` → toolbox.db Download (Admin only)

## Frontend-Architektur

### Contexts
- `AuthContext` — user, loading, login(), logout(), isAdmin
- `BrandingContext` — app_name, animation_theme, custom_subtitle, loading, setBranding; setzt document.title
- `ToastContext` — toast(message, type) mit Auto-Dismiss

### Key Components
- `Layout` — Desktop-Sidebar (md+) + Mobile Bottom-Nav + Mobile Top-Bar mit User-Dropdown; PasswordDialog
- `StartupAnimation` — 4 Themes (hofblick/koppel/hufspur/stallgefluester), einmal pro Session (sessionStorage), preview-mode für Admin-Seite
- `Skeleton.jsx` — SkeletonTableRows, SkeletonCards, SkeletonStatCards, SkeletonChart
- `ErrorBoundary` — React-Klasse, fängt alle unbehandelten Fehler
- `OfflineBanner` — reagiert auf window online/offline Events

### Routing
```
/login
/dashboard
/admin/users          (AdminRoute)
/admin/branding       (AdminRoute)
/reittagebuch/neu     (+ ?id=X für Edit-Modus)
/reittagebuch/uebersicht
/reittagebuch/auswertungen
/reittagebuch/tiere
/reittagebuch/export
```

## Design-Entscheidungen
- Tailwind v4 via `@tailwindcss/vite`, `@import "tailwindcss"` in CSS, `@theme { --font-* }`
- Google Fonts: DM Sans (UI), DM Serif Display (Serif-Überschriften), Baloo 2 + Caveat + Quicksand (Animations-Themes)
- Farben: `#5b7c5e` primary grün, `#faf8f4` bg, `#2a7ab5` Kinder-Blau, `#7c3aed` Jugendliche-Lila
- JWT 24h, python-jose, bcrypt via passlib
- Default-Admin: admin/admin (Lifespan-Hook, nur wenn DB leer)
- Tiere: soft-delete (aktiv=False), Einträge: hard-delete
- SQLAlchemy lädt tiere über selectinload via secondary join table

## Bekannte Besonderheiten / Fallstricke
- `PUT /api/users/me/password` muss VOR `PUT /api/users/{id}` definiert sein (FastAPI Path-Matching)
- Vite-Build → `frontend/dist/`; FastAPI mountet `/assets` + Catch-All für SPA-Routing
- CORS: `localhost:5173` (Dev) + same-origin (Prod) explizit erlaubt
- Startup-Animation wartet auf BrandingContext-Load (`!loading`) bevor sie angezeigt wird
- Kein `node_modules/` committen (.gitignore: `node_modules/`, `frontend/dist/`, `data/`, `venv/`)

## Aktueller Stand
- [x] Phase 1: Projekt-Setup, Auth-System, Dashboard, User-Verwaltung
- [x] Phase 2: Reittagebuch (Einträge, Tiere, Stats/Charts, Excel-Export, DB-Backup)
- [x] Phase 2.5: UX-Polish (Skeleton-Loader, Mobile Bottom-Nav, ErrorBoundary, Offline-Banner, Passwort-Ändern, Letzte-Aktivität-Widget)
- [x] Phase 3: Branding-System (AppSettings, 4 Startup-Animations-Themes, Admin-Konfigurationsseite)
- [x] Deployment-Scripts (start.bat/sh + dev.bat/sh mit venv-Management)
- [ ] Phase 4: Cloud-Deployment (Cloudflare Pages + Supabase Postgres)
- [ ] Weitere Tools (Druckkosten-Kalkulation, ...)

## Letzte Änderungen
- 2026-06-08: Projekt vollständig initialisiert (Phasen 1–3 abgeschlossen)
- 2026-06-08: Branding-System: AppSettings-Model, /api/settings/branding, BrandingContext, StartupAnimation (4 Themes: hofblick/koppel/hufspur/stallgefluester), BrandingSettings-Adminseite
- 2026-06-08: UX-Verbesserungen: Skeleton-Loader, Mobile Bottom-Nav, PasswordDialog, OfflineBanner, ErrorBoundary, Letzte-Aktivität-Dashboard-Widget, Mobile-Kartenansicht in Overview
- 2026-06-08: Deployment-Scripts: start.bat/sh (mit venv + build-check), dev.bat/sh (Backend --reload + Frontend parallel)
