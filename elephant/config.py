from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ELEPHANT_", env_file=".env")

    ollama_url: str = "http://localhost:11434"
    model_name: str = "llama3"
    memories_base_path: Path = Path(__file__).parent / "data" / "memories"


settings = Settings()
