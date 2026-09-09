"""One sign-in for the whole system.

A single `users` table backs both the maintenance report admin area and the ICT
help desk, so ICT staff hold one set of credentials. Capability is read from the
account: `is_admin` for the admin area, `helpdesk_role` for the help desk.
"""

from functools import wraps

from flask import flash, redirect, request, session, url_for

from extensions import db
from models import User


SESSION_KEY = "user_id"


def current_user() -> User | None:
    user_id = session.get(SESSION_KEY)
    if not user_id:
        return None

    user = db.session.get(User, user_id)
    if user and user.is_active:
        return user
    session.pop(SESSION_KEY, None)
    return None


def current_admin() -> User | None:
    user = current_user()
    return user if user and user.is_admin else None


def login_user(user: User) -> None:
    session[SESSION_KEY] = user.id


def logout_user() -> None:
    session.pop(SESSION_KEY, None)


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_admin() is None:
            flash("Administrator sign-in required.", "warning")
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def manager_required(view):
    """ICT managers — and the system admin — may edit a submitted report."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Sign in as an ICT manager to edit a report.", "warning")
            return redirect(url_for("login", next=request.full_path))
        if not user.is_manager:
            flash("Only an ICT manager may edit a submitted report.", "danger")
            return redirect(url_for("submissions"))
        return view(*args, **kwargs)

    return wrapped


def signed_in_required(view):
    """Any account on the platform — role is checked separately where it matters."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Sign in to view complaints.", "warning")
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def landing_page_for(user: User) -> str:
    """Send each account to the area it actually works in."""
    if user.is_admin:
        return url_for("admin")
    if user.is_helpdesk_staff:
        return url_for("helpdesk.dashboard")
    return url_for("maintenance_form")
