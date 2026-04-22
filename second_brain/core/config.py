from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
VAULT_DIR = BASE_DIR / "data" / "vault"
CHROMA_DIR = BASE_DIR / "data" / "chroma_db"
DB_PATH = BASE_DIR / "data" / "second_brain.db"

OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
CHAT_MODEL = "llama3"

APP_NAME = "SecondBrain Agent"
VERSION = "1.0.0"
