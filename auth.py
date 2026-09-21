"""One sign-in for the whole system.

A single `users` table backs both the maintenance report admin area and the ICT
help desk, so ICT staff hold one set of credentials. Capability is read from the
account: `is_admin` for the admin area, `helpdesk_role` for the help desk.

The portal itself is closed: `register_access_gate` turns every route into a
signed-in route, and PUBLIC_ENDPOINTS is the short, explicit list of exceptions.
Gating this way rather than decorator-by-decorator means a route added later is
private until somebody deliberately names it public here.
"""

from functools import wraps

from flask import flash, redirect, request, session, url_for

from extensions import db
from models import User


SESSION_KEY = "user_id"

# The only endpoints reachable without an account.
#
# The help desk intake is public by design: a member of staff whose computer
# has failed reports it, and is given a tracking link, without ever holding an
# account. Those reporter routes prove ownership with the link's token instead
# (see HELP_DESK/access.py).
PUBLIC_ENDPOINTS = frozenset(
    {
        "static",
        "login",
        "logout",
        "signup",
        "confirm_email",
        "resend_confirmation",
        "helpdesk.static",
        "helpdesk.new_ticket",
        "helpdesk.track_ticket",
        "helpdesk.view_ticket",
        "helpdesk.reporter_comment",
        "helpdesk.reporter_status",
    }
)


def register_access_gate(app) -> None:
    """Close the portal: everything but PUBLIC_ENDPOINTS needs an account."""

    @app.before_request
    def require_signed_in_user():
        endpoint = request.endpoint

        # No endpoint means no route matched; let it fall through to the 404
        # rather than answering an unknown URL with a sign-in redirect.
        if endpoint is None or endpoint in PUBLIC_ENDPOINTS:
            return None
        if current_user() is not None:
            return None

        flash("Sign in to use the ICT portal.", "warning")
        return redirect(url_for("login", next=request.full_path))


def current_user() -> User | None:
    user_id = session.get(SESSION_KEY)
    if not user_id:
        return None

    user = db.session.get(User, user_id)
    # Re-checked on every request, not just at sign-in, so deactivating an
    # account ends the session it already holds.
    if user and user.may_sign_in:
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
