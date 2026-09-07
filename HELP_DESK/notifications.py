"""Email sent to the ICT help desk when a complaint is submitted."""

from flask import url_for

from HELP_DESK.models import Ticket, as_utc
from mailer import best_effort, send_email


@best_effort
def email_new_ticket(ticket: Ticket) -> bool:
    subject = f"[Help Desk] {ticket.reference} · {ticket.priority_label} · {ticket.subject}"
    return send_email(
        subject=subject,
        body=_body(ticket),
        # ICT can reply straight to the person who reported it.
        reply_to=ticket.reporter_email,
    )


def _body(ticket: Ticket) -> str:
    reporter = ticket.reporter_name
    if ticket.reporter_email:
        reporter = f"{reporter} <{ticket.reporter_email}>"

    lines = [
        "A new complaint has been submitted to the ICT help desk.",
        "",
        f"Reference:   {ticket.reference}",
        f"Priority:    {ticket.priority_label}",
        f"Problem:     {ticket.category_summary}",
        f"Summary:     {ticket.subject}",
        "",
        f"Reported by: {reporter}",
        f"Department:  {ticket.department}",
        f"Location:    {ticket.location or '—'}",
        f"Computer:    {ticket.computer_name or '—'}",
        f"Submitted:   {as_utc(ticket.created_at).strftime('%Y-%m-%d %H:%M')} UTC",
        f"Target:      {as_utc(ticket.due_at).strftime('%Y-%m-%d %H:%M')} UTC"
        if ticket.due_at
        else "Target:      —",
        "",
        "Description",
        "-----------",
        ticket.description,
    ]

    if ticket.category_key == "other" and ticket.other_category:
        lines += ["", "Problem type, in the reporter's words", "-" * 37, ticket.other_category]

    link = _dashboard_link(ticket)
    if link:
        lines += ["", f"Open the ticket: {link}"]

    return "\n".join(lines)


def _dashboard_link(ticket: Ticket) -> str | None:
    try:
        return url_for("helpdesk.view_ticket", reference=ticket.reference, _external=True)
    except RuntimeError:
        # No request or SERVER_NAME configured; the email is still worth sending.
        return None
