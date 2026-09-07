from conftest import create_user, sign_in, sign_out, submit_complaint

from HELP_DESK import catalog
from HELP_DESK.models import Ticket
from models import User


def latest_ticket(app):
    with app.app_context():
        return Ticket.query.order_by(Ticket.id.desc()).first()


def token_for(app, reference):
    with app.app_context():
        return Ticket.query.filter_by(reference=reference).one().access_token


def test_helpdesk_roles_live_on_the_one_user_table(app):
    with app.app_context():
        manager = User.query.filter_by(username="ictmanager").one()
        officer = User.query.filter_by(username="icthelpdesk").one()
        admin = User.query.filter_by(username="jonyango").one()

        assert manager.helpdesk_role == "manager" and manager.is_manager
        assert officer.helpdesk_role == "officer" and officer.is_manager is False
        assert officer.is_helpdesk_staff

        # The maintenance admin is one account, usable in both areas.
        assert admin.is_admin and admin.is_manager

        # Every seeded account uses the same password.
        for user in (manager, officer, admin):
            assert user.check_password("field.123")

        assert Ticket.query.count() == 2


def test_form_lists_every_category_including_other(client):
    response = client.get("/helpdesk/")

    assert response.status_code == 200
    for key, label in catalog.category_choices():
        assert key.encode() in response.data
    assert b"Other (describe the problem below)" in response.data


def test_submit_complaint_creates_ticket_with_reference_and_sla(client, app):
    response = submit_complaint(client)

    assert response.status_code == 302
    ticket = latest_ticket(app)

    assert ticket.reference.startswith("HD-")
    assert ticket.access_token
    assert ticket.status == "open"
    # Priority comes from the category, not from the reporter.
    assert ticket.priority == catalog.default_priority("printer")
    assert ticket.due_at is not None
    assert f"token={ticket.access_token}" in response.headers["Location"]


def test_urgent_category_gets_urgent_priority(client, app):
    submit_complaint(
        client,
        category_key="virus_malware",
        subject="Pop-ups asking for my password",
        description="Strange pop-ups appeared after opening an attachment.",
    )

    assert latest_ticket(app).priority == "urgent"


def test_other_category_requires_free_text(client, app):
    before = latest_ticket(app).id

    response = submit_complaint(client, category_key="other", other_category="")

    assert b"Describe the problem type" in response.data
    assert latest_ticket(app).id == before


def test_other_category_is_stored_and_displayed(client, app):
    submit_complaint(
        client,
        category_key="other",
        other_category="Desk phone has no dial tone",
        subject="Desk phone dead",
        description="No dial tone since the power cut this morning.",
    )
    ticket = latest_ticket(app)

    assert ticket.category_key == "other"
    assert ticket.category_label == "Desk phone has no dial tone"


def test_invalid_submissions_are_rejected(client, app):
    before = latest_ticket(app).id

    response = client.post("/helpdesk/", data={"category_key": "printer"}, follow_redirects=True)

    assert b"Your name is required." in response.data
    assert b"Department is required." in response.data
    assert b"A short summary is required." in response.data
    assert b"at least 10 characters" in response.data
    assert latest_ticket(app).id == before


def test_ticket_view_requires_token_or_signed_in_staff(client, app):
    submit_complaint(client)
    ticket = latest_ticket(app)

    assert client.get(f"/helpdesk/ticket/{ticket.reference}").status_code == 403
    assert client.get(f"/helpdesk/ticket/{ticket.reference}?token=wrong").status_code == 403
    assert client.get(f"/helpdesk/ticket/{ticket.reference}?token={ticket.access_token}").status_code == 200


def test_staff_can_open_any_ticket_without_token(client, app):
    submit_complaint(client)
    reference = latest_ticket(app).reference

    sign_in(client)

    assert client.get(f"/helpdesk/ticket/{reference}").status_code == 200


def test_track_page_finds_ticket_with_reference_and_token(client, app):
    submit_complaint(client)
    ticket = latest_ticket(app)

    response = client.post(
        "/helpdesk/track",
        data={"reference": ticket.reference, "token": ticket.access_token},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert ticket.reference in response.headers["Location"]

    bad = client.post("/helpdesk/track", data={"reference": ticket.reference, "token": "nope"}, follow_redirects=True)
    assert b"No ticket matches" in bad.data


def test_reporter_can_report_their_own_problem_resolved(client, app):
    submit_complaint(client)
    ticket = latest_ticket(app)

    response = client.post(
        f"/helpdesk/ticket/{ticket.reference}/status?token={ticket.access_token}",
        data={"status": "resolved", "message": "It started working after a restart."},
        follow_redirects=True,
    )

    assert b"help desk has been notified" in response.data
    with app.app_context():
        saved = Ticket.query.filter_by(reference=ticket.reference).one()
        assert saved.status == "resolved"
        assert saved.resolved_by == "Jane Reporter"
        assert saved.resolution_notes == "It started working after a restart."


def test_reporter_can_close_their_resolved_ticket(client, app):
    submit_complaint(client)
    ticket = latest_ticket(app)
    url = f"/helpdesk/ticket/{ticket.reference}/status?token={ticket.access_token}"

    client.post(url, data={"status": "resolved"})
    client.post(url, data={"status": "closed"})

    with app.app_context():
        saved = Ticket.query.filter_by(reference=ticket.reference).one()
        assert saved.status == "closed"
        assert saved.closed_by == "Jane Reporter"


def test_reporter_reopen_clears_resolution_and_counts(client, app):
    submit_complaint(client)
    ticket = latest_ticket(app)
    url = f"/helpdesk/ticket/{ticket.reference}/status?token={ticket.access_token}"

    client.post(url, data={"status": "resolved", "message": "Seemed fine."})
    client.post(url, data={"status": "open", "message": "It has come back."})

    with app.app_context():
        saved = Ticket.query.filter_by(reference=ticket.reference).one()
        assert saved.status == "open"
        assert saved.reopen_count == 1
        assert saved.resolved_at is None
        assert saved.resolved_by is None


def test_reporter_cannot_skip_the_workflow(client, app):
    submit_complaint(client)
    ticket = latest_ticket(app)

    response = client.post(
        f"/helpdesk/ticket/{ticket.reference}/status?token={ticket.access_token}",
        data={"status": "closed"},
        follow_redirects=True,
    )

    assert b"not available for this ticket" in response.data
    with app.app_context():
        assert Ticket.query.filter_by(reference=ticket.reference).one().status == "open"


def test_officer_cannot_close_but_manager_can(client, app):
    submit_complaint(client)
    reference = latest_ticket(app).reference

    sign_in(client, "icthelpdesk")
    client.post(f"/helpdesk/staff/ticket/{reference}/status", data={"status": "resolved", "message": "Replaced toner."})
    denied = client.post(f"/helpdesk/staff/ticket/{reference}/status", data={"status": "closed"}, follow_redirects=True)

    assert b"Only the ICT manager or the reporter can close" in denied.data
    with app.app_context():
        assert Ticket.query.filter_by(reference=reference).one().status == "resolved"

    sign_out(client)
    sign_in(client, "ictmanager")
    client.post(f"/helpdesk/staff/ticket/{reference}/status", data={"status": "closed"}, follow_redirects=True)

    with app.app_context():
        saved = Ticket.query.filter_by(reference=reference).one()
        assert saved.status == "closed"
        assert saved.closed_by == "ICT Manager"


def test_resolution_notes_are_required_for_staff(client, app):
    submit_complaint(client)
    reference = latest_ticket(app).reference
    sign_in(client)

    response = client.post(
        f"/helpdesk/staff/ticket/{reference}/status",
        data={"status": "resolved", "message": ""},
        follow_redirects=True,
    )

    assert b"Add resolution notes" in response.data
    with app.app_context():
        assert Ticket.query.filter_by(reference=reference).one().status == "open"


def test_assignment_moves_ticket_into_progress(client, app):
    submit_complaint(client)
    reference = latest_ticket(app).reference
    sign_in(client)

    with app.app_context():
        officer_id = User.query.filter_by(username="icthelpdesk").one().id

    client.post(f"/helpdesk/staff/ticket/{reference}/assign", data={"staff_id": officer_id}, follow_redirects=True)

    with app.app_context():
        saved = Ticket.query.filter_by(reference=reference).one()
        assert saved.assigned_to_id == officer_id
        assert saved.status == "in_progress"


def test_priority_change_recalculates_the_sla_target(client, app):
    submit_complaint(client)
    reference = latest_ticket(app).reference
    sign_in(client)

    with app.app_context():
        original_due = Ticket.query.filter_by(reference=reference).one().due_at

    client.post(f"/helpdesk/staff/ticket/{reference}/priority", data={"priority": "urgent"}, follow_redirects=True)

    with app.app_context():
        saved = Ticket.query.filter_by(reference=reference).one()
        assert saved.priority == "urgent"
        assert saved.due_at < original_due


def test_every_action_is_written_to_the_audit_trail(client, app):
    submit_complaint(client)
    ticket = latest_ticket(app)
    sign_in(client)

    client.post(f"/helpdesk/staff/ticket/{ticket.reference}/comment", data={"message": "Looking into it now."})
    client.post(
        f"/helpdesk/staff/ticket/{ticket.reference}/status",
        data={"status": "resolved", "message": "Cleared the stuck print queue."},
    )

    with app.app_context():
        saved = Ticket.query.filter_by(reference=ticket.reference).one()
        kinds = [event.event_type for event in saved.events]
        actors = {event.actor_role for event in saved.events}

        assert kinds == ["created", "comment", "status"]
        assert actors == {"reporter", "officer"}
        assert saved.first_response_at is not None


def test_dashboard_requires_login_and_shows_queue(client, app):
    submit_complaint(client)

    redirected = client.get("/helpdesk/staff", follow_redirects=False)
    assert redirected.status_code == 302
    assert "/login" in redirected.headers["Location"]

    sign_in(client)
    dashboard = client.get("/helpdesk/staff")

    assert dashboard.status_code == 200
    assert b"Help Desk Dashboard" in dashboard.data
    assert b"Printer will not print" in dashboard.data


def test_dashboard_active_queue_is_ordered_by_priority(client, app):
    submit_complaint(client, category_key="software_install", subject="Need Adobe Reader",
                     description="Please install Adobe Reader on my laptop.")
    submit_complaint(client, category_key="virus_malware", subject="Suspicious pop-ups",
                     description="Pop-ups appeared after opening an email attachment.")
    sign_in(client)

    body = client.get("/helpdesk/staff?status=active").data.decode()

    assert body.index("Suspicious pop-ups") < body.index("Need Adobe Reader")


def test_csv_export_contains_submitted_tickets(client, app):
    submit_complaint(client)
    sign_in(client)

    response = client.get("/helpdesk/staff/export.csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["Content-Type"]
    assert b"Printer will not print" in response.data
    assert b"Reference,Status,Priority" in response.data


def test_unknown_ticket_returns_404(client):
    assert client.get("/helpdesk/ticket/HD-2026-9999?token=x").status_code == 404


def test_one_credential_works_across_both_areas(client, app):
    """The point of unifying: jonyango signs in once and can use admin and help desk."""
    submit_complaint(client)
    reference = latest_ticket(app).reference

    sign_in(client, "jonyango", "field.123")

    # Admin area.
    assert client.get("/admin").status_code == 200
    assert client.get("/admin/records").status_code == 200

    # Help desk, same session — and as a manager they may close.
    assert client.get("/helpdesk/staff").status_code == 200
    client.post(
        f"/helpdesk/staff/ticket/{reference}/status",
        data={"status": "resolved", "message": "Cleared the print queue."},
    )
    client.post(f"/helpdesk/staff/ticket/{reference}/status", data={"status": "closed"})

    with app.app_context():
        saved = Ticket.query.filter_by(reference=reference).one()
        assert saved.status == "closed"
        assert saved.closed_by == "ICT Administrator"


def test_a_plain_user_account_has_no_help_desk_access(client, app):
    sign_in(client, "jonyango", "field.123")
    create_user(client, "plain_user")
    sign_out(client)

    sign_in(client, "plain_user", "field.123")

    redirected = client.get("/helpdesk/staff", follow_redirects=False)
    assert redirected.status_code == 302
    assert "/login" in redirected.headers["Location"]

    # They can still raise a ticket like anyone else.
    assert client.get("/helpdesk/").status_code == 200


def test_tickets_can_only_be_assigned_to_help_desk_accounts(client, app):
    submit_complaint(client)
    reference = latest_ticket(app).reference

    sign_in(client, "jonyango", "field.123")
    create_user(client, "plain_user")

    with app.app_context():
        plain_user_id = User.query.filter_by(username="plain_user").one().id

    response = client.post(
        f"/helpdesk/staff/ticket/{reference}/assign",
        data={"staff_id": plain_user_id},
        follow_redirects=True,
    )

    assert b"Choose a help desk officer" in response.data
    with app.app_context():
        assert Ticket.query.filter_by(reference=reference).one().assigned_to_id is None
