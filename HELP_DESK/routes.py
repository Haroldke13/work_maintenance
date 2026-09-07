import csv
import io
import json

from flask import abort, flash, redirect, render_template, request, url_for

from auth import current_user, signed_in_required
from extensions import db
from HELP_DESK import catalog, services
from HELP_DESK.access import (
    current_staff,
    reporter_authorized,
    require_reporter,
    staff_required,
    ticket_by_reference,
)
from HELP_DESK.blueprint import helpdesk_bp
from HELP_DESK.models import Ticket, as_utc
from models import User


@helpdesk_bp.context_processor
def inject_helpdesk_context():
    return {
        "catalog": catalog,
        "staff": current_staff(),
        "self_help_json": json.dumps(
            {item["key"]: item["self_help"] for item in catalog.PROBLEM_CATEGORIES}
        ),
    }


@helpdesk_bp.app_template_filter("moment")
def moment(value):
    value = as_utc(value)
    return value.strftime("%Y-%m-%d %H:%M") if value else "—"


# --------------------------------------------------------------------------- #
# Reporter routes
# --------------------------------------------------------------------------- #

@helpdesk_bp.route("/", methods=["GET", "POST"])
def new_ticket():
    form_data = {
        "reporter_name": "",
        "reporter_email": "",
        "department": "",
        "location": "",
        "computer_name": "",
        "category_key": "",
        "other_category": "",
        "subject": "",
        "description": "",
    }

    if request.method == "POST":
        form_data = {key: request.form.get(key, "").strip() for key in form_data}
        errors = validate_ticket_form(form_data)

        if errors:
            for error in errors:
                flash(error, "danger")
        else:
            ticket = services.create_ticket(form_data)
            flash(f"Complaint received. Your reference is {ticket.reference}.", "success")
            return redirect(
                url_for("helpdesk.view_ticket", reference=ticket.reference, token=ticket.access_token)
            )

    return render_template("helpdesk/new_ticket.html", form_data=form_data)


@helpdesk_bp.route("/track", methods=["GET", "POST"])
def track_ticket():
    if request.method == "POST":
        reference = request.form.get("reference", "").strip().upper()
        token = request.form.get("token", "").strip()
        ticket = Ticket.query.filter_by(reference=reference).first()

        if ticket and reporter_authorized(ticket, token):
            return redirect(url_for("helpdesk.view_ticket", reference=reference, token=token))
        flash("No ticket matches that reference and tracking code.", "danger")

    return render_template("helpdesk/track.html")


@helpdesk_bp.route("/ticket/<reference>")
def view_ticket(reference: str):
    ticket = ticket_by_reference(reference)
    token = request.args.get("token")
    staff = current_staff()

    if not reporter_authorized(ticket, token) and current_user() is None:
        abort(403)

    return render_template(
        "helpdesk/ticket.html",
        ticket=ticket,
        token=token if reporter_authorized(ticket, token) else None,
        staff=staff,
        viewer_is_reporter=reporter_authorized(ticket, token),
        staff_members=helpdesk_members(),
    )


@helpdesk_bp.route("/ticket/<reference>/comment", methods=["POST"])
def reporter_comment(reference: str):
    ticket = ticket_by_reference(reference)
    token = require_reporter(ticket)
    message = request.form.get("message", "").strip()

    if not message:
        flash("Write a message before sending it.", "danger")
    else:
        services.add_comment(ticket, message, ticket.reporter_name, "reporter")
        flash("Message sent to the help desk.", "success")

    return redirect(url_for("helpdesk.view_ticket", reference=reference, token=token))


@helpdesk_bp.route("/ticket/<reference>/status", methods=["POST"])
def reporter_status(reference: str):
    """The reporter can report it fixed itself, close it, or reopen it."""
    ticket = ticket_by_reference(reference)
    token = require_reporter(ticket)
    new_status = request.form.get("status", "")
    message = request.form.get("message", "").strip() or None

    allowed = {
        "resolved": ticket.is_open,
        "closed": ticket.status == "resolved",
        "open": ticket.status in ("resolved", "closed"),
    }
    if not allowed.get(new_status):
        flash("That action is not available for this ticket right now.", "danger")
        return redirect(url_for("helpdesk.view_ticket", reference=reference, token=token))

    services.change_status(ticket, new_status, ticket.reporter_name, "reporter", message)

    notices = {
        "resolved": "Thank you — the help desk has been notified that your problem is resolved.",
        "closed": "Ticket closed. Thank you for confirming.",
        "open": "Ticket reopened. The help desk has been notified.",
    }
    flash(notices[new_status], "success")
    return redirect(url_for("helpdesk.view_ticket", reference=reference, token=token))


@helpdesk_bp.route("/complaints")
@signed_in_required
def complaints():
    """Tracker of every complaint on the platform, for any account holder."""
    status_filter = request.args.get("status", "all")
    search = request.args.get("q", "").strip()

    query = Ticket.query
    if status_filter == "active":
        query = query.filter(Ticket.status.in_(catalog.OPEN_STATUSES))
    elif status_filter in catalog.STATUSES:
        query = query.filter(Ticket.status == status_filter)

    if search:
        pattern = f"%{search}%"
        query = query.filter(
            db.or_(
                Ticket.reference.ilike(pattern),
                Ticket.subject.ilike(pattern),
                Ticket.reporter_name.ilike(pattern),
                Ticket.department.ilike(pattern),
                Ticket.computer_name.ilike(pattern),
            )
        )

    tickets = query.order_by(Ticket.created_at.desc()).all()

    return render_template(
        "helpdesk/complaints.html",
        tickets=tickets,
        stats=services.dashboard_stats(),
        total=Ticket.query.count(),
        status_filter=status_filter,
        search=search,
    )


# --------------------------------------------------------------------------- #
# Help desk staff routes
# --------------------------------------------------------------------------- #

@helpdesk_bp.route("/staff")
@staff_required
def dashboard():
    status_filter = request.args.get("status", "active")
    query = Ticket.query

    if status_filter == "active":
        query = query.filter(Ticket.status.in_(catalog.OPEN_STATUSES))
    elif status_filter in catalog.STATUSES:
        query = query.filter(Ticket.status == status_filter)

    staff = current_staff()

    if status_filter == "mine":
        query = Ticket.query.filter(
            Ticket.assigned_to_id == staff.id,
            Ticket.status.in_(catalog.OPEN_STATUSES),
        )
    elif status_filter == "unassigned":
        query = Ticket.query.filter(
            Ticket.assigned_to_id.is_(None),
            Ticket.status.in_(catalog.OPEN_STATUSES),
        )

    tickets = query.order_by(Ticket.created_at.desc()).all()
    if status_filter == "active":
        tickets = services.sorted_open_tickets()

    return render_template(
        "helpdesk/dashboard.html",
        staff=staff,
        tickets=tickets,
        stats=services.dashboard_stats(),
        status_filter=status_filter,
        staff_members=helpdesk_members(),
        mine_count=Ticket.query.filter(
            Ticket.assigned_to_id == staff.id,
            Ticket.status.in_(catalog.OPEN_STATUSES),
        ).count(),
    )


@helpdesk_bp.route("/staff/ticket/<reference>/comment", methods=["POST"])
@staff_required
def staff_comment(reference: str):
    ticket = ticket_by_reference(reference)
    staff = current_staff()
    message = request.form.get("message", "").strip()

    if not message:
        flash("Write a message before sending it.", "danger")
    else:
        services.add_comment(ticket, message, staff.display_name, staff.helpdesk_actor_role)
        flash("Reply added.", "success")

    return redirect(url_for("helpdesk.view_ticket", reference=reference))


@helpdesk_bp.route("/staff/ticket/<reference>/status", methods=["POST"])
@staff_required
def staff_status(reference: str):
    ticket = ticket_by_reference(reference)
    staff = current_staff()
    new_status = request.form.get("status", "")
    message = request.form.get("message", "").strip() or None

    if new_status not in catalog.STATUSES:
        abort(400)

    # Closing a ticket is deliberately restricted: only the person who reported
    # the problem or an ICT manager may declare it finished.
    if new_status == "closed" and not staff.is_manager:
        flash("Only the ICT manager or the reporter can close a ticket.", "danger")
        return redirect(url_for("helpdesk.view_ticket", reference=reference))

    if new_status == "resolved" and not message:
        flash("Add resolution notes before marking a ticket resolved.", "danger")
        return redirect(url_for("helpdesk.view_ticket", reference=reference))

    services.change_status(ticket, new_status, staff.display_name, staff.helpdesk_actor_role, message)
    flash(f"Ticket {reference} is now {catalog.STATUSES[new_status]['label']}.", "success")
    return redirect(url_for("helpdesk.view_ticket", reference=reference))


def may_reassign(ticket, staff) -> bool:
    """The person holding the ticket can move it on; so can a manager.

    An unheld ticket is free for anyone on the help desk to pick up.
    """
    return (
        ticket.assigned_to_id is None
        or ticket.assigned_to_id == staff.id
        or staff.is_manager
    )


def back_to(reference: str):
    """Queue actions return to the queue; ticket-page actions return to the ticket."""
    if request.form.get("origin") == "queue":
        return redirect(url_for("helpdesk.dashboard", status=request.form.get("status") or None))
    return redirect(url_for("helpdesk.view_ticket", reference=reference))


@helpdesk_bp.route("/staff/ticket/<reference>/claim", methods=["POST"])
@staff_required
def staff_claim(reference: str):
    """Pick up a task from the queue."""
    ticket = ticket_by_reference(reference)
    staff = current_staff()

    if ticket.assigned_to_id == staff.id:
        flash(f"{reference} is already yours.", "info")
    elif not may_reassign(ticket, staff):
        flash(
            f"{reference} is with {ticket.assigned_to.display_name}. "
            "Ask them to return it, or ask the ICT manager to transfer it.",
            "danger",
        )
    else:
        services.assign_ticket(ticket, staff, staff.display_name, staff.helpdesk_actor_role)
        flash(f"You picked up {reference}.", "success")

    return back_to(reference)


@helpdesk_bp.route("/staff/ticket/<reference>/release", methods=["POST"])
@staff_required
def staff_release(reference: str):
    """Return a task to the queue for someone else to take."""
    ticket = ticket_by_reference(reference)
    staff = current_staff()

    if ticket.assigned_to_id is None:
        flash(f"{reference} is already in the queue.", "info")
    elif not may_reassign(ticket, staff):
        flash("Only the assignee or the ICT manager can return this task.", "danger")
    else:
        services.release_ticket(ticket, staff.display_name, staff.helpdesk_actor_role)
        flash(f"{reference} is back in the queue.", "success")

    return back_to(reference)


@helpdesk_bp.route("/staff/ticket/<reference>/assign", methods=["POST"])
@staff_required
def staff_assign(reference: str):
    """Transfer a task to another member of the help desk."""
    ticket = ticket_by_reference(reference)
    staff = current_staff()
    assignee = db.session.get(User, request.form.get("staff_id", type=int))
    if assignee is not None and not (assignee.is_helpdesk_staff or assignee.is_admin):
        assignee = None

    if assignee is None:
        flash("Choose a help desk officer to assign.", "danger")
    elif not may_reassign(ticket, staff):
        flash(
            f"{reference} is with {ticket.assigned_to.display_name}. "
            "Only they or the ICT manager can transfer it.",
            "danger",
        )
    else:
        services.assign_ticket(ticket, assignee, staff.display_name, staff.helpdesk_actor_role)
        flash(
            f"You picked up {reference}." if assignee.id == staff.id
            else f"{reference} transferred to {assignee.display_name}.",
            "success",
        )

    return back_to(reference)


@helpdesk_bp.route("/staff/ticket/<reference>/priority", methods=["POST"])
@staff_required
def staff_priority(reference: str):
    ticket = ticket_by_reference(reference)
    staff = current_staff()
    priority = request.form.get("priority", "")

    if priority not in catalog.PRIORITIES:
        abort(400)

    services.set_priority(ticket, priority, staff.display_name, staff.helpdesk_actor_role)
    flash("Priority updated.", "success")
    return redirect(url_for("helpdesk.view_ticket", reference=reference))


@helpdesk_bp.route("/staff/export.csv")
@staff_required
def export_csv():
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Reference", "Status", "Priority", "Category", "Subject",
            "Reporter", "Department", "Computer", "Assigned To",
            "Created", "Due", "Resolved", "Minutes To Resolve", "Reopened",
        ]
    )
    for ticket in Ticket.query.order_by(Ticket.id).all():
        writer.writerow(
            [
                ticket.reference, ticket.status_label, ticket.priority_label,
                ticket.category_label, ticket.subject, ticket.reporter_name,
                ticket.department, ticket.computer_name or "",
                ticket.assigned_to.display_name if ticket.assigned_to else "",
                as_utc(ticket.created_at).strftime("%Y-%m-%d %H:%M"),
                as_utc(ticket.due_at).strftime("%Y-%m-%d %H:%M") if ticket.due_at else "",
                as_utc(ticket.resolved_at).strftime("%Y-%m-%d %H:%M") if ticket.resolved_at else "",
                ticket.minutes_to_resolve if ticket.minutes_to_resolve is not None else "",
                ticket.reopen_count,
            ]
        )

    return (
        buffer.getvalue(),
        200,
        {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": "attachment; filename=helpdesk-tickets.csv",
        },
    )


def helpdesk_members() -> list[User]:
    """Accounts that can be assigned a ticket."""
    return (
        User.query.filter(
            User.is_active.is_(True),
            db.or_(User.helpdesk_role.isnot(None), User.is_admin.is_(True)),
        )
        .order_by(User.username)
        .all()
    )


def validate_ticket_form(form_data: dict) -> list[str]:
    errors = []

    if not form_data["reporter_name"]:
        errors.append("Your name is required.")
    if not form_data["department"]:
        errors.append("Department is required.")
    if not catalog.is_valid_category(form_data["category_key"]):
        errors.append("Choose the problem type from the list.")
    elif form_data["category_key"] == catalog.OTHER_KEY and not form_data["other_category"]:
        errors.append("Describe the problem type for the 'Other' option.")
    if not form_data["subject"]:
        errors.append("A short summary is required.")
    if len(form_data["description"]) < 10:
        errors.append("Describe the problem in at least 10 characters.")

    return errors
