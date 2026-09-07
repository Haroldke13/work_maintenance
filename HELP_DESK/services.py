"""Ticket operations shared by the reporter and staff routes.

Every state change goes through one of these helpers so the audit trail and the
Socket.IO broadcasts can never drift apart from the database.
"""

from sqlalchemy import func

from extensions import db, socketio
from HELP_DESK import catalog
from HELP_DESK.models import Ticket, TicketEvent, as_utc, utcnow
from models import STAFF_ACTOR_ROLES


HELPDESK_ROOM = "helpdesk"


def ticket_room(reference: str) -> str:
    return f"ticket:{reference}"


# --------------------------------------------------------------------------- #
# Broadcasting
# --------------------------------------------------------------------------- #

def broadcast(event: str, payload: dict, reference: str | None = None) -> None:
    """Push to the help desk dashboard, and to anyone watching that one ticket."""
    socketio.emit(event, payload, to=HELPDESK_ROOM)
    if reference:
        socketio.emit(event, payload, to=ticket_room(reference))


def broadcast_stats() -> None:
    socketio.emit("stats", dashboard_stats(), to=HELPDESK_ROOM)


def dashboard_stats() -> dict:
    counts = dict(
        db.session.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
    )
    open_tickets = Ticket.query.filter(Ticket.status.in_(catalog.OPEN_STATUSES)).all()
    resolved = Ticket.query.filter(Ticket.resolved_at.isnot(None)).all()

    resolution_minutes = [t.minutes_to_resolve for t in resolved if t.minutes_to_resolve is not None]
    average_minutes = round(sum(resolution_minutes) / len(resolution_minutes)) if resolution_minutes else None

    return {
        "open": counts.get("open", 0),
        "in_progress": counts.get("in_progress", 0),
        "resolved": counts.get("resolved", 0),
        "closed": counts.get("closed", 0),
        "overdue": sum(1 for ticket in open_tickets if ticket.is_overdue),
        "unassigned": sum(1 for ticket in open_tickets if ticket.assigned_to_id is None),
        "average_resolution_minutes": average_minutes,
    }


# --------------------------------------------------------------------------- #
# Audit trail
# --------------------------------------------------------------------------- #

def record_event(
    ticket: Ticket,
    event_type: str,
    actor_name: str,
    actor_role: str,
    message: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
) -> TicketEvent:
    event = TicketEvent(
        ticket=ticket,
        event_type=event_type,
        actor_name=actor_name,
        actor_role=actor_role,
        message=message,
        from_status=from_status,
        to_status=to_status,
    )
    db.session.add(event)
    return event


# --------------------------------------------------------------------------- #
# Ticket operations
# --------------------------------------------------------------------------- #

def create_ticket(data: dict) -> Ticket:
    category_key = data["category_key"]
    priority = data.get("priority") or catalog.default_priority(category_key)

    ticket = Ticket(
        access_token=Ticket.new_access_token(),
        category_key=category_key,
        other_category=data.get("other_category") or None,
        subject=data["subject"],
        description=data["description"],
        reporter_name=data["reporter_name"],
        reporter_email=data.get("reporter_email") or None,
        department=data["department"],
        location=data.get("location") or None,
        computer_name=data.get("computer_name") or None,
        priority=priority,
        status="open",
        reference="",
    )
    db.session.add(ticket)
    db.session.flush()  # assigns ticket.id
    ticket.assign_reference()
    ticket.apply_sla()

    record_event(
        ticket,
        event_type="created",
        actor_name=ticket.reporter_name,
        actor_role="reporter",
        message=ticket.description,
        to_status="open",
    )
    db.session.commit()

    socketio.emit("ticket:created", ticket.to_dict(), to=HELPDESK_ROOM)
    broadcast_stats()

    # Emailed after the commit, so a mail problem can never lose the complaint.
    from HELP_DESK.notifications import email_new_ticket

    email_new_ticket(ticket)
    return ticket


def add_comment(ticket: Ticket, message: str, actor_name: str, actor_role: str) -> TicketEvent:
    if actor_role in STAFF_ACTOR_ROLES and ticket.first_response_at is None:
        ticket.first_response_at = utcnow()

    event = record_event(
        ticket,
        event_type="comment",
        actor_name=actor_name,
        actor_role=actor_role,
        message=message,
    )
    ticket.updated_at = utcnow()
    db.session.commit()

    payload = {"ticket": ticket.to_dict(), "event": event.to_dict()}
    broadcast("ticket:comment", payload, ticket.reference)
    return event


def change_status(
    ticket: Ticket,
    new_status: str,
    actor_name: str,
    actor_role: str,
    message: str | None = None,
) -> Ticket:
    previous_status = ticket.status
    ticket.status = new_status
    ticket.updated_at = utcnow()

    if new_status == "resolved":
        ticket.resolved_at = utcnow()
        ticket.resolved_by = actor_name
        if message:
            ticket.resolution_notes = message
    elif new_status == "closed":
        ticket.closed_at = utcnow()
        ticket.closed_by = actor_name
    elif new_status in catalog.OPEN_STATUSES and previous_status in ("resolved", "closed"):
        # Reopening: the earlier resolution no longer stands.
        ticket.reopen_count += 1
        ticket.resolved_at = None
        ticket.resolved_by = None
        ticket.closed_at = None
        ticket.closed_by = None
        ticket.apply_sla()

    if actor_role in STAFF_ACTOR_ROLES and ticket.first_response_at is None:
        ticket.first_response_at = utcnow()

    event = record_event(
        ticket,
        event_type="status",
        actor_name=actor_name,
        actor_role=actor_role,
        message=message,
        from_status=previous_status,
        to_status=new_status,
    )
    db.session.commit()

    payload = {"ticket": ticket.to_dict(), "event": event.to_dict()}
    broadcast("ticket:updated", payload, ticket.reference)

    if new_status == "resolved":
        # The explicit "a problem has been resolved" alert for the help desk.
        socketio.emit(
            "ticket:resolved",
            {
                "reference": ticket.reference,
                "subject": ticket.subject,
                "resolved_by": actor_name,
                "resolved_by_role": actor_role,
                "self_resolved": actor_role == "reporter",
                "minutes_to_resolve": ticket.minutes_to_resolve,
                "ticket": ticket.to_dict(),
            },
            to=HELPDESK_ROOM,
        )

    broadcast_stats()
    return ticket


def assign_ticket(ticket: Ticket, staff, actor_name: str, actor_role: str) -> Ticket:
    """Give the ticket to someone. Picking it up yourself is the same operation."""
    previous = ticket.assigned_to
    ticket.assigned_to = staff
    ticket.updated_at = utcnow()
    if ticket.status == "open":
        ticket.status = "in_progress"

    if staff is not None and previous is not None and previous.id != staff.id:
        message = f"Transferred from {previous.display_name} to {staff.display_name}."
    elif staff is not None and staff.display_name == actor_name:
        message = f"Picked up by {staff.display_name}."
    else:
        message = f"Assigned to {staff.display_name}."

    event = record_event(
        ticket,
        event_type="assignment",
        actor_name=actor_name,
        actor_role=actor_role,
        message=message,
    )
    db.session.commit()

    broadcast("ticket:updated", {"ticket": ticket.to_dict(), "event": event.to_dict()}, ticket.reference)
    broadcast_stats()
    return ticket


def release_ticket(ticket: Ticket, actor_name: str, actor_role: str) -> Ticket:
    """Hand a ticket back to the unassigned pool so somebody else can pick it up."""
    previous = ticket.assigned_to
    ticket.assigned_to = None
    ticket.updated_at = utcnow()
    if ticket.status == "in_progress":
        ticket.status = "open"

    event = record_event(
        ticket,
        event_type="assignment",
        actor_name=actor_name,
        actor_role=actor_role,
        message=(
            f"Returned to the queue by {actor_name}."
            if previous is None or previous.display_name == actor_name
            else f"Returned to the queue (was with {previous.display_name})."
        ),
    )
    db.session.commit()

    broadcast("ticket:updated", {"ticket": ticket.to_dict(), "event": event.to_dict()}, ticket.reference)
    broadcast_stats()
    return ticket


def set_priority(ticket: Ticket, priority: str, actor_name: str, actor_role: str) -> Ticket:
    previous = ticket.priority
    ticket.priority = priority
    ticket.apply_sla()
    ticket.updated_at = utcnow()

    event = record_event(
        ticket,
        event_type="priority",
        actor_name=actor_name,
        actor_role=actor_role,
        message=(
            f"Priority changed from {catalog.PRIORITIES[previous]['label']} "
            f"to {catalog.PRIORITIES[priority]['label']}."
        ),
    )
    db.session.commit()

    broadcast("ticket:updated", {"ticket": ticket.to_dict(), "event": event.to_dict()}, ticket.reference)
    broadcast_stats()
    return ticket


def sorted_open_tickets() -> list[Ticket]:
    """Most urgent first, then oldest first — the order the help desk should work in."""
    tickets = Ticket.query.filter(Ticket.status.in_(catalog.OPEN_STATUSES)).all()
    return sorted(
        tickets,
        key=lambda t: (catalog.PRIORITIES[t.priority]["rank"], as_utc(t.created_at)),
    )
