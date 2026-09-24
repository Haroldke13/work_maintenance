"""Every submitted response is emailed only to the configured recipient."""

from conftest import sign_in, submit_complaint
from test_routes import valid_maintenance_form

from mailer import send_email
from models import User


RECIPIENTS = "jonyango@pbora.go.ke"


def test_new_complaint_is_emailed_only_to_jonyango(client, outbox):
    submit_complaint(client)

    assert len(outbox) == 1
    message = outbox[0]

    assert message["To"] == RECIPIENTS
    assert "Printer will not print" in message["Subject"]
    assert message["Subject"].startswith("[Help Desk] HD-")
    # ICT can reply straight to the reporter.
    assert message["Reply-To"] == "jane@example.org"

    body = message.get_content()
    assert "Jane Reporter <jane@example.org>" in body
    assert "Finance Office" in body
    assert "Documents queue but nothing comes out of the printer." in body
    assert "NGOB-PC-002" in body


def test_maintenance_report_is_emailed_only_to_jonyango(client, outbox):
    sign_in(client)
    outbox.clear()
    client.post("/maintenance", data=valid_maintenance_form())

    assert len(outbox) == 1
    message = outbox[0]

    assert message["To"] == RECIPIENTS
    assert message["Subject"].startswith("[Maintenance Report] ROUTE-PC")

    body = message.get_body(preferencelist=("plain",)).get_content()
    assert "Route Coverage Officer" in body
    assert "1. Computer and peripherals cleaned?: Yes" in body
    assert "12. Disk defragmentation done?: No" in body

    attachments = list(message.iter_attachments())
    assert len(attachments) == 1
    pdf = attachments[0]
    assert pdf.get_content_type() == "application/pdf"
    assert pdf.get_filename().startswith("maintenance-report-")
    assert pdf.get_payload(decode=True).startswith(b"%PDF-1.4")
    assert pdf.get_payload(decode=True).rstrip().endswith(b"%%EOF")


def test_free_text_problem_type_reaches_the_email(client, outbox):
    long_description = (
        "The desk phone has no dial tone at all, and the handset cable looks\n"
        "frayed near the base unit. It started after the power cut."
    )
    submit_complaint(
        client,
        category_key="other",
        other_category=long_description,
        subject="Desk phone dead",
        description="No dial tone since the power cut this morning.",
    )

    body = outbox[0].get_content()

    assert "Problem type, in the reporter's words" in body
    assert "frayed near the base unit" in body
    # The subject stays on one short line even though the field is a textarea.
    assert "\n" not in outbox[0]["Subject"]
    assert len(outbox[0]["Subject"]) < 160


def test_platform_accounts_are_not_added_to_notification_recipients(app, client, outbox):
    with app.app_context():
        from extensions import db

        registry = User(username="registry_head", email="registry@pbora.go.ke")
        registry.set_password("field.123")
        db.session.add(registry)
        db.session.commit()

    submit_complaint(client)

    assert "registry@pbora.go.ke" not in outbox[0]["To"]
    assert outbox[0]["To"] == RECIPIENTS


def test_nothing_is_sent_when_there_is_nobody_to_send_to(app, client, outbox):
    app.config["NOTIFY_EMAILS"] = []

    submit_complaint(client)

    assert outbox == []


def test_a_mail_failure_never_loses_the_submission(app, client, monkeypatch):
    """SMTP is best-effort: the ticket must still be saved and acknowledged."""
    from HELP_DESK.models import Ticket
    import mailer

    def explode(*args, **kwargs):
        raise RuntimeError("SMTP is down")

    monkeypatch.setattr(mailer, "send_email", explode)
    from HELP_DESK import notifications

    monkeypatch.setattr(notifications, "send_email", explode)

    response = submit_complaint(client, subject="Mail server is down")

    assert response.status_code == 302
    with app.app_context():
        assert Ticket.query.filter_by(subject="Mail server is down").one().status == "open"


def test_send_email_skips_when_credentials_are_missing(app):
    app.config["MAIL_SUPPRESS_SEND"] = False
    app.config["MAIL_USERNAME"] = ""

    with app.test_request_context("/"):
        assert send_email("Subject", "Body") is False


def test_jonyango_account_pegs_to_its_address(app):
    with app.app_context():
        admin = User.query.filter_by(username="jonyango").one()

        assert admin.email == "jonyango@pbora.go.ke"


def test_sender_shows_the_organisation_not_the_gmail_account(client, outbox):
    submit_complaint(client)

    assert outbox[0]["From"] == "PBORA <helpdesk-test@example.org>"


def test_sender_name_is_configurable(app, client, outbox):
    app.config["MAIL_SENDER_NAME"] = "PBORA ICT Help Desk"

    submit_complaint(client)

    assert outbox[0]["From"] == "PBORA ICT Help Desk <helpdesk-test@example.org>"
