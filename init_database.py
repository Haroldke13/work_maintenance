#!/usr/bin/env python
"""Auto-initialize the database and guarantee the `jonyango` administrator.

Run it against a brand new database or an existing one:

    python init_database.py

It creates any missing tables, stamps Alembic at the current head so later
`flask db upgrade` runs start from the right place, seeds the sample data, and
makes sure the administrator account exists with the default password.
"""

import sys

from flask import Flask

from app import create_app, seed_database
from extensions import db
from models import User


def stamp_migrations(app: Flask) -> None:
    """Mark the schema as up to date; harmless when Alembic is not configured."""
    try:
        from flask_migrate import stamp
    except ImportError:
        return

    with app.app_context():
        try:
            stamp(revision="head")
        except Exception as error:  # a missing migrations/ directory, mostly
            print(f"Skipped stamping migrations: {error}")


def ensure_admin(app: Flask) -> User:
    """Create or repair the administrator named in ADMIN_USERNAME (jonyango)."""
    username = app.config["ADMIN_USERNAME"]
    password = app.config["ADMIN_PASSWORD"]

    with app.app_context():
        user = User.query.filter_by(username=username).first()
        created = user is None

        if created:
            user = User(username=username)
            db.session.add(user)

        user.full_name = user.full_name or "ICT Administrator"
        user.email = user.email or app.config["ADMIN_EMAIL"]
        user.is_admin = True
        user.helpdesk_role = "manager"
        user.is_active = True
        user.receives_notifications = True
        user.set_password(password)

        db.session.commit()
        print(
            f"Administrator '{username}' {'created' if created else 'updated'} "
            f"with password '{password}'."
        )
        return user


def main() -> int:
    app = create_app()

    with app.app_context():
        db.create_all()
    print("Database tables are ready.")

    stamp_migrations(app)

    seed_database(app)
    print("Seed data is ready.")

    ensure_admin(app)
    return 0


if __name__ == "__main__":
    sys.exit(main())
