"""The Complaints tracker and its navbar badge."""

from conftest import create_user, sign_in, submit_complaint

from HELP_DESK.models import Ticket
from models import User


def test_tracker_requires_an_account(client):
    response = client.get("/helpdesk/complaints", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_any_account_can_view_every_complaint(client, app):
    submit_complaint(client, subject="Printer jam in Registry")
    submit_complaint(client, subject="Laptop will not charge", category_key="battery_power")

    sign_in(client, "jonyango", "field.123")
    create_user(client, "plain_user")
    client.post("/logout")
    sign_in(client, "plain_user", "field.123")

    response = client.get("/helpdesk/complaints")

    assert response.status_code == 200
    assert b"Complaints Tracker" in response.data
    assert b"Printer jam in Registry" in response.data
    assert b"Laptop will not charge" in response.data
    # Seeded tickets are there too — it tracks the whole platform.
    assert b"Finance printer will not print payment vouchers" in response.data


def test_tracker_filters_by_status(client, app):
    submit_complaint(client, subject="Still broken")

    with app.app_context():
        reference = Ticket.query.filter_by(subject="Still broken").one().reference

    sign_in(client, "icthelpdesk", "field.123")
    client.post(
        f"/helpdesk/staff/ticket/{reference}/status",
        data={"status": "resolved", "message": "Fixed it."},
    )

    resolved = client.get("/helpdesk/complaints?status=resolved")
    assert b"Still broken" in resolved.data

    open_only = client.get("/helpdesk/complaints?status=open")
    assert b"Still broken" not in open_only.data


def test_tracker_search_matches_reference_and_department(client, app):
    submit_complaint(client, subject="Scanner offline", department="Registry")
    sign_in(client, "icthelpdesk", "field.123")

    by_department = client.get("/helpdesk/complaints?q=Registry")
    assert b"Scanner offline" in by_department.data

    with app.app_context():
        reference = Ticket.query.filter_by(subject="Scanner offline").one().reference

    by_reference = client.get(f"/helpdesk/complaints?q={reference}")
    assert b"Scanner offline" in by_reference.data

    no_match = client.get("/helpdesk/complaints?q=zzzznothing")
    assert b"No complaints match this view" in no_match.data


def test_navbar_shows_complaints_button_with_a_count(client, app):
    submit_complaint(client, subject="One")
    submit_complaint(client, subject="Two")

    with app.app_context():
        expected = Ticket.query.count()

    sign_in(client, "jonyango", "field.123")

    for page in ("/maintenance", "/admin", "/helpdesk/", "/helpdesk/complaints"):
        body = client.get(page).data.decode()
        assert "/helpdesk/complaints" in body, page
        assert ">Complaints" in body or "Complaints\n" in body, page
        assert f">{expected}</span>" in body, page


def test_navbar_hides_complaints_button_when_signed_out(client):
    body = client.get("/maintenance").data.decode()

    assert "/helpdesk/complaints" not in body
    # The public complaint form is still reachable.
    assert "/helpdesk/" in body


def test_signed_in_account_can_read_a_ticket_without_the_token(client, app):
    submit_complaint(client, subject="Readable ticket")
    with app.app_context():
        reference = Ticket.query.filter_by(subject="Readable ticket").one().reference

    assert client.get(f"/helpdesk/ticket/{reference}").status_code == 403

    sign_in(client, "jonyango", "field.123")
    create_user(client, "reader")
    client.post("/logout")
    sign_in(client, "reader", "field.123")

    response = client.get(f"/helpdesk/ticket/{reference}")

    assert response.status_code == 200
    assert b"Readable ticket" in response.data
    # A plain account gets no help desk action panel.
    assert b"Mark resolved" not in response.data
    assert b"Help Desk Actions" not in response.data


def test_admin_can_leave_an_account_off_the_mail_list(client, app):
    sign_in(client, "jonyango", "field.123")

    create_user(client, "quiet_user", email="quiet@pbora.go.ke")

    with app.app_context():
        # The checkbox is absent from the post, so the account is left off.
        quiet = User.query.filter_by(username="quiet_user").one()
        assert quiet.receives_notifications is False
        assert quiet.is_mail_recipient is False

    create_user(client, "loud_user", email="loud@pbora.go.ke",
                receives_notifications="on")

    with app.app_context():
        loud = User.query.filter_by(username="loud_user").one()
        assert loud.receives_notifications is True
        assert loud.is_mail_recipient is True
