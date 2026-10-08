import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
	database_url: str
	redis_url: str
	public_base_url: str


settings = Settings(
	database_url=os.getenv(
		"DATABASE_URL",
		"postgresql+psycopg2://backend_user:backend-password@localhost:5432/backend_db",
	),
	redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
	public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
)
