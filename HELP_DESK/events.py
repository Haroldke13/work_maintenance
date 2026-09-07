"""Socket.IO handlers. Room membership is authorised server-side, never by the client.

Registration is a function, not an import side effect: Flask-SocketIO binds a handler
to whichever server exists at decoration time, so handlers applied once at import
would only ever reach the first app created in a process (and every test builds one).
"""

from flask_socketio import join_room

from extensions import socketio
from HELP_DESK import services
from HELP_DESK.access import current_staff, reporter_authorized
from HELP_DESK.models import Ticket


def register_socket_events() -> None:
    @socketio.on("join_dashboard")
    def handle_join_dashboard(data=None):
        """Only a signed-in help desk session receives the live queue."""
        if current_staff() is None:
            return {"joined": False, "reason": "not_authorised"}

        join_room(services.HELPDESK_ROOM)
        return {"joined": True, "stats": services.dashboard_stats()}

    @socketio.on("join_ticket")
    def handle_join_ticket(data=None):
        reference = (data or {}).get("reference", "")
        token = (data or {}).get("token")
        ticket = Ticket.query.filter_by(reference=reference).first()

        if ticket is None:
            return {"joined": False, "reason": "not_found"}
        if not reporter_authorized(ticket, token) and current_staff() is None:
            return {"joined": False, "reason": "not_authorised"}

        join_room(services.ticket_room(reference))
        return {"joined": True, "ticket": ticket.to_dict()}
