from pydantic_settings import BaseSettings


class Config(BaseSettings):
    SESSION_TIMEOUT_MINUTES: int = 60
    SECRET_KEY: str = "change-me-in-production"
    DB_URL: str = "sqlite:///./mainframe.db"


config = Config()
