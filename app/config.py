from os import getenv


class Settings:
    database_url: str = getenv("DATABASE_URL", "sqlite+aiosqlite:///data/symlinkrepair.db")
    data_dir: str = getenv("DATA_DIR", "data")


settings = Settings()
