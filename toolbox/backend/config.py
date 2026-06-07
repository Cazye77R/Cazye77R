import secrets

SECRET_KEY = secrets.token_hex(32)  # in Produktion als ENV-Variable
DATABASE_URL = "sqlite:///./data/toolbox.db"  # Für Postgres/Supabase: postgresql://user:pass@host/db
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 Tag
