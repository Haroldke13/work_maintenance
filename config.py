import os

from dotenv import load_dotenv


load_dotenv()


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://cleanup_user:cleanup_password@localhost:5433/cleanup_practical",
        )
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "jonyango")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "field.123")
    DEFAULT_USER_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "field.123")
