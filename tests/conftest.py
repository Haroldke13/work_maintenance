import pytest

from app import create_app, initialize_database
from config import Config
from models import db


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "route-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ADMIN_USERNAME = "jonyango"
    ADMIN_PASSWORD = "field.123"
    DEFAULT_USER_PASSWORD = "field.123"


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
