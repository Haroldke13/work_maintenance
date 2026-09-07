import pytest

from app import create_app, initialize_database
from config import Config
from extensions import db, socketio


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "route-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = "jonyango"
    ADMIN_PASSWORD = "field.123"
    DEFAULT_USER_PASSWORD = "field.123"
    HELPDESK_MANAGER_USERNAME = "ictmanager"
    HELPDESK_MANAGER_PASSWORD = "field.123"
    HELPDESK_OFFICER_USERNAME = "icthelpdesk"
    HELPDESK_OFFICER_PASSWORD = "field.123"
    SERVER_NAME = "maintenance.test"
    MAIL_SUPPRESS_SEND = True
    MAIL_USERNAME = "helpdesk-test@example.org"
    MAIL_DEFAULT_SENDER = "helpdesk-test@example.org"
    NOTIFY_EMAILS = ["jonyango@pbora.go.ke", "ictsupport@pbora.go.ke"]


@pytest.fixture
def app():
    test_app = create_app(TestConfig)
    initialize_database(test_app)

    yield test_app

    with test_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def outbox(app):
    """Notification emails captured instead of sent."""
    from mailer import outbox as mail_outbox

    box = mail_outbox(app)
    box.clear()
    return box


@pytest.fixture
def sio(app, client):
    """Socket.IO test client sharing the Flask session with `client`."""

    def _connect():
        return socketio.test_client(app, flask_test_client=client)

    return _connect


def submit_complaint(client, follow_redirects=False, **overrides):
    data = {
        "reporter_name": "Jane Reporter",
        "reporter_email": "jane@example.org",
        "department": "Finance Office",
        "location": "2nd Floor",
        "computer_name": "NGOB-PC-002",
        "category_key": "printer",
        "other_category": "",
        "subject": "Printer will not print",
        "description": "Documents queue but nothing comes out of the printer.",
    }
    data.update(overrides)
    return client.post("/helpdesk/", data=data, follow_redirects=follow_redirects)


def sign_in(client, username="icthelpdesk", password="field.123"):
    """One sign-in for admin and help desk alike. Every seeded password is field.123."""
    return client.post(
        "/login",
        data={"username": username, "password": password},
        follow_redirects=True,
    )


def sign_out(client):
    return client.post("/logout", follow_redirects=True)


def create_user(client, username, **fields):
    """Create an account through the admin console. Caller must be signed in as admin."""
    data = {"username": username}
    data.update(fields)
    return client.post("/admin/users/new", data=data, follow_redirects=True)
