"""Emails sent when a report is submitted, and when an account is created."""

from flask import current_app, url_for

from form_schema import FIELD_SECTIONS, is_signature_data_url
from mailer import best_effort, send_email
from models import MaintenanceReport, User


@best_effort
def email_new_account(user: User, how: str) -> bool:
    """Tell ICT that an account now exists. `how` says where it came from.

    Goes to the configured ICT addresses only — the administrator and the
    shared inbox. Not to the account holder, who has their own mail about it,
    and deliberately not to the wider notification list a report goes to: who
    holds an account is ICT's business, not every user's.

    Self-service signup is the case that matters: nobody on staff was
    involved, so this is the only trace of it that reaches a person.
    """
    subject = f"[ICT Portal] New account: {user.username}"
    body = "\n".join(
        [
            "An account has been created on the PBO Regulatory Authority ICT portal.",
            "",
            f"Username : {user.username}",
            f"Email    : {user.email or '—'}",
            f"Full name: {user.full_name or '—'}",
            f"Created  : {how}",
            f"Rights   : {user.role_label}",
            "",
            "Review it, or change what it may do, under Admin > Users.",
        ]
    )
    return send_email(
        subject=subject,
        body=body,
        recipients=current_app.config.get("NOTIFY_EMAILS") or [],
    )


@best_effort
def email_maintenance_report(report: MaintenanceReport) -> bool:
    subject = (
        f"[Maintenance Report] {report.computer_name} · {report.department} "
        f"· {report.report_date:%Y-%m-%d}"
    )
    return send_email(subject=subject, body=_body(report))


def _body(report: MaintenanceReport) -> str:
    lines = [
        "A Computer Maintenance Report (NGOB/ICT/104b) has been submitted.",
        "",
        f"Chassis model: {report.computer_name}",
        f"Department:    {report.department}",
        f"Officer:       {report.officer_name}",
        f"Date:          {report.report_date:%Y-%m-%d}",
        "",
    ]

    for section in FIELD_SECTIONS:
        lines.append(section["title"])
        lines.append("-" * len(section["title"]))
        for field in section["fields"]:
            lines.append(f"{field['label']}: {_render(report.value_for(field['name']))}")
        lines.append("")

    link = _report_link(report)
    if link:
        lines.append(f"View the report: {link}")

    return "\n".join(lines)


def _render(value) -> str:
    # A drawn signature is a PNG data URL; the email says it is there rather
    # than carrying kilobytes of base64.
    if is_signature_data_url(value):
        return "(signed)"
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    if value in (None, ""):
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M" if hasattr(value, "hour") else "%Y-%m-%d")
    return str(value)


def _report_link(report: MaintenanceReport) -> str | None:
    try:
        return url_for("table", report_id=report.id, _external=True)
    except RuntimeError:
        return None
