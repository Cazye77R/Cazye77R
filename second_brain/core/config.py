from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
VAULT_DIR = BASE_DIR / "data" / "vault"
CHROMA_DIR = BASE_DIR / "data" / "chroma_db"
DB_PATH = BASE_DIR / "data" / "second_brain.db"

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3"

APP_NAME = "SecondBrain Agent"
VERSION = "1.0.0"

# Ensure data directory exists before engine creation
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    # Pool settings suited for a single-user desktop app
    pool_size=5,
    max_overflow=10,
)
SessionFactory = scoped_session(sessionmaker(bind=engine, autoflush=False))
