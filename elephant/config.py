from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    embedding_model: str = "nomic-embed-text"
    memory_path: Path = Path(__file__).parent / "data" / "memories"
    chroma_path: Path = Path(__file__).parent.parent / "data" / "chroma"
    top_k: int = 5
    chunk_size: int = 2000    # characters (~500 tokens)
    chunk_overlap: int = 200  # characters (~50 tokens)
    decay_rate: float = 0.01  # importance reduction per day
    consolidation_threshold: float = 0.8


settings = Settings()
