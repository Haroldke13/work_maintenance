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
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "jonyango@pbora.go.ke")
    SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "ictsupport@pbora.go.ke")
    DEFAULT_USER_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "field.123")

    # Help desk (served by the HELP_DESK blueprint on this same app and port).
    HELPDESK_MANAGER_USERNAME = os.getenv("HELPDESK_MANAGER_USERNAME", "ictmanager")
    HELPDESK_MANAGER_PASSWORD = os.getenv("HELPDESK_MANAGER_PASSWORD", "field.123")
    HELPDESK_OFFICER_USERNAME = os.getenv("HELPDESK_OFFICER_USERNAME", "icthelpdesk")
    HELPDESK_OFFICER_PASSWORD = os.getenv("HELPDESK_OFFICER_PASSWORD", "field.123")

    # Email notifications. Every submitted response is mailed to NOTIFY_EMAILS.
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").strip().lower() in ("1", "true", "yes")
    MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER") or os.getenv("MAIL_USERNAME", "")
    # The name recipients see in their inbox, instead of the Gmail account name.
    MAIL_SENDER_NAME = os.getenv("MAIL_SENDER_NAME", "PBORA")
    MAIL_TIMEOUT = int(os.getenv("MAIL_TIMEOUT", "20"))
    # How long a signup confirmation link stays valid. Long enough to survive a
    # weekend and a slow mail queue; `/confirm/resend` issues a fresh one.
    EMAIL_CONFIRM_MAX_AGE = int(os.getenv("EMAIL_CONFIRM_MAX_AGE", str(72 * 3600)))
    MAIL_SUPPRESS_SEND = False
    NOTIFY_EMAILS = [
        address.strip()
        for address in os.getenv(
            "NOTIFY_EMAILS", "jonyango@pbora.go.ke"
        ).split(",")
        if address.strip()
    ]
