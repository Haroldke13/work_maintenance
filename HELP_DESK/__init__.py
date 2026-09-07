"""ICT help desk: complaints, ticketing, and live Socket.IO notifications.

This is a blueprint inside the maintenance report app, not a separate service, so
it is served on the same host and port and the "Report a Problem" button works
whenever Flask is run from the project root.
"""

from HELP_DESK.blueprint import helpdesk_bp
from HELP_DESK.seed_data import seed_helpdesk


__all__ = ["helpdesk_bp", "seed_helpdesk", "register_helpdesk"]


def register_helpdesk(app, url_prefix: str = "/helpdesk") -> None:
    """Mount the help desk and its Socket.IO handlers onto an existing app."""
    from HELP_DESK import routes  # noqa: F401  (attaches views to the blueprint)
    from HELP_DESK.events import register_socket_events

    register_socket_events()
    if "helpdesk" not in app.blueprints:
        app.register_blueprint(helpdesk_bp, url_prefix=url_prefix)
