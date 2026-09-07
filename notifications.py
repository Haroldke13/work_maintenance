"""Email sent when a computer maintenance report is submitted."""

from flask import url_for

from form_schema import FIELD_SECTIONS
from mailer import best_effort, send_email
from models import MaintenanceReport


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
        f"Computer:   {report.computer_name}",
        f"Department: {report.department}",
        f"Officer:    {report.officer_name}",
        f"Date:       {report.report_date:%Y-%m-%d}",
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
