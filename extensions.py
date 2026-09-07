"""Extensions shared by the maintenance report app and the help desk blueprint."""

from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()
migrate = Migrate()

# "threading" keeps the app runnable under the plain Flask server, gunicorn's
# gthread worker, and pytest without monkey-patching the standard library.
socketio = SocketIO(async_mode="threading", cors_allowed_origins="*")
