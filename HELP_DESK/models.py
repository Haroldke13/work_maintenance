import secrets
from datetime import datetime, timedelta, timezone

from extensions import db
from HELP_DESK import catalog
from models import User  # noqa: F401  (Ticket.assigned_to targets it)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; compare everything in UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False, index=True)
    access_token = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # What is wrong
    category_key = db.Column(db.String(40), nullable=False)
    other_category = db.Column(db.Text, nullable=True)
    subject = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False)

    # Who reported it
    reporter_name = db.Column(db.String(120), nullable=False)
    reporter_email = db.Column(db.String(160), nullable=True)
    department = db.Column(db.String(120), nullable=False)
    location = db.Column(db.String(120), nullable=True)
    computer_name = db.Column(db.String(120), nullable=True)

    # Handling
    priority = db.Column(db.String(20), nullable=False, default="normal")
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)
    due_at = db.Column(db.DateTime(timezone=True), nullable=True)
    first_response_at = db.Column(db.DateTime(timezone=True), nullable=True)

    resolved_at = db.Column(db.DateTime(timezone=True), nullable=True)
    resolved_by = db.Column(db.String(120), nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    closed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    closed_by = db.Column(db.String(120), nullable=True)
    reopen_count = db.Column(db.Integer, nullable=False, default=0)

    assigned_to = db.relationship("User")
    events = db.relationship(
        "TicketEvent",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketEvent.created_at",
    )

    @staticmethod
    def new_access_token() -> str:
        return secrets.token_urlsafe(24)

    def assign_reference(self) -> None:
        """Called after flush, so the row id is available."""
        year = as_utc(self.created_at or utcnow()).year
        self.reference = f"HD-{year}-{self.id:04d}"

    def apply_sla(self) -> None:
        hours = catalog.sla_hours(self.priority)
        self.due_at = as_utc(self.created_at or utcnow()) + timedelta(hours=hours)

    @property
    def category_label(self) -> str:
        return catalog.category_label(self.category_key, self.other_category)

    @property
    def category_summary(self) -> str:
        """One short line, for tables and notification subjects.

        An "Other" ticket carries whatever the reporter typed into a textarea,
        which can run to several lines.
        """
        label = (self.category_label or "").strip()
        first_line = label.splitlines()[0] if label else ""
        return first_line if len(first_line) <= 60 else first_line[:57].rstrip() + "…"

    @property
    def status_label(self) -> str:
        return catalog.STATUSES.get(self.status, {}).get("label", self.status)

    @property
    def status_badge(self) -> str:
        return catalog.STATUSES.get(self.status, {}).get("badge", "secondary")

    @property
    def priority_label(self) -> str:
        return catalog.PRIORITIES.get(self.priority, {}).get("label", self.priority)

    @property
    def priority_badge(self) -> str:
        return catalog.PRIORITIES.get(self.priority, {}).get("badge", "secondary")

    @property
    def is_open(self) -> bool:
        return self.status in catalog.OPEN_STATUSES

    @property
    def is_overdue(self) -> bool:
        """Only unresolved tickets can breach their SLA."""
        if not self.is_open or self.due_at is None:
            return False
        return utcnow() > as_utc(self.due_at)

    @property
    def minutes_to_resolve(self) -> int | None:
        if self.resolved_at is None:
            return None
        delta = as_utc(self.resolved_at) - as_utc(self.created_at)
        return int(delta.total_seconds() // 60)

    def to_dict(self) -> dict:
        """Payload broadcast over Socket.IO and rendered by the dashboard."""
        return {
            "reference": self.reference,
            "subject": self.subject,
            "category": self.category_summary,
            "reporter_name": self.reporter_name,
            "department": self.department,
            "computer_name": self.computer_name,
            "priority": self.priority,
            "priority_label": self.priority_label,
            "priority_badge": self.priority_badge,
            "status": self.status,
            "status_label": self.status_label,
            "status_badge": self.status_badge,
            "assigned_to": self.assigned_to.display_name if self.assigned_to else None,
            "created_at": as_utc(self.created_at).strftime("%Y-%m-%d %H:%M"),
            "due_at": as_utc(self.due_at).strftime("%Y-%m-%d %H:%M") if self.due_at else None,
            "is_overdue": self.is_overdue,
            "reopen_count": self.reopen_count,
            "resolution_notes": self.resolution_notes,
        }


class TicketEvent(db.Model):
    """Append-only audit trail: who did what to a ticket, and when."""

    __tablename__ = "ticket_events"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"), nullable=False, index=True)
    event_type = db.Column(db.String(30), nullable=False)  # created|comment|status|assignment|priority
    actor_name = db.Column(db.String(120), nullable=False)
    actor_role = db.Column(db.String(20), nullable=False)  # reporter|officer|manager|system
    message = db.Column(db.Text, nullable=True)
    from_status = db.Column(db.String(20), nullable=True)
    to_status = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    ticket = db.relationship("Ticket", back_populates="events")

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "actor_name": self.actor_name,
            "actor_role": self.actor_role,
            "message": self.message,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "created_at": as_utc(self.created_at).strftime("%Y-%m-%d %H:%M"),
        }
