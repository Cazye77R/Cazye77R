import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, SessionLocal, engine
from .models import User
from .auth import get_password_hash
from .routers.users import auth_router, users_router
from .routers.reittagebuch import router as reittagebuch_router

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            admin = User(
                username="admin",
                display_name="Administrator",
                hashed_password=get_password_hash("admin"),
                is_active=True,
                is_admin=True,
            )
            db.add(admin)
            db.commit()
            print("⚠️  Standard-Admin erstellt (admin/admin) — bitte Passwort ändern!")
    finally:
        db.close()
    yield


app = FastAPI(title="Toolbox", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:8000",  # Production same-origin
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(reittagebuch_router)

# Serve React frontend static assets (production)
if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_react(full_path: str):
    # Serve specific static files if they exist (favicon, manifest, etc.)
    candidate = FRONTEND_DIST / full_path
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    # Fallback to index.html for React Router (SPA)
    index = FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"detail": "Frontend not built. Run: cd frontend && npm run build"}
