"""Who may see and change a ticket.

Reporters have no account: they prove ownership with the token from the tracking
link they were given. Help desk access is a role on the shared `users` account,
so ICT staff sign in once for the whole system.
"""

from functools import wraps

from flask import abort, flash, redirect, request, url_for

from auth import current_user
from HELP_DESK.models import Ticket
from models import User


def current_staff() -> User | None:
    """The signed-in user, but only if their account carries a help desk role."""
    user = current_user()
    if user and (user.is_helpdesk_staff or user.is_admin):
        return user
    return None


def staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_staff() is None:
            flash("Help desk sign-in required.", "warning")
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapped


def ticket_by_reference(reference: str) -> Ticket:
    ticket = Ticket.query.filter_by(reference=reference).first()
    if ticket is None:
        abort(404)
    return ticket


def reporter_authorized(ticket: Ticket, token: str | None) -> bool:
    return bool(token) and token == ticket.access_token


def require_reporter(ticket: Ticket) -> str:
    token = request.values.get("token")
    if not reporter_authorized(ticket, token):
        abort(403)
    return token
