"""Picking, returning and transferring tasks from the work queue."""

import pytest

from conftest import create_user, sign_in, sign_out, submit_complaint

from extensions import db
from HELP_DESK.models import Ticket
from models import User


@pytest.fixture
def intern(app):
    """An ICT intern account — interns work the queue like officers."""
    with app.app_context():
        user = User(username="intern_ann", full_name="Ann Intern", helpdesk_role="intern")
        user.set_password("field.123")
        db.session.add(user)
        db.session.commit()
        return user.id


def a_ticket(client, app, subject="Queue task"):
    submit_complaint(client, subject=subject)
    with app.app_context():
        return Ticket.query.filter_by(subject=subject).one().reference


def ticket_state(app, reference):
    with app.app_context():
        ticket = Ticket.query.filter_by(reference=reference).one()
        return ticket.status, (ticket.assigned_to.username if ticket.assigned_to else None)


def test_intern_can_reach_the_work_queue(client, app, intern):
    sign_in(client, "intern_ann", "field.123")

    response = client.get("/helpdesk/staff")

    assert response.status_code == 200
    assert b"Help Desk Dashboard" in response.data
    assert b"Ann Intern (ICT intern)" in response.data


def test_officer_picks_a_task_off_the_queue(client, app):
    reference = a_ticket(client, app)
    sign_in(client, "icthelpdesk", "field.123")

    response = client.post(
        f"/helpdesk/staff/ticket/{reference}/claim",
        data={"origin": "queue", "status": "active"},
        follow_redirects=True,
    )

    assert b"You picked up" in response.data
    assert ticket_state(app, reference) == ("in_progress", "icthelpdesk")


def test_intern_picks_and_returns_a_task(client, app, intern):
    reference = a_ticket(client, app)
    sign_in(client, "intern_ann", "field.123")

    client.post(f"/helpdesk/staff/ticket/{reference}/claim", follow_redirects=True)
    assert ticket_state(app, reference) == ("in_progress", "intern_ann")

    returned = client.post(f"/helpdesk/staff/ticket/{reference}/release", follow_redirects=True)

    assert b"back in the queue" in returned.data
    # Returning puts it back in the unassigned pool, not into limbo.
    assert ticket_state(app, reference) == ("open", None)


def test_intern_transfers_a_task_to_another_account(client, app, intern):
    reference = a_ticket(client, app)
    sign_in(client, "intern_ann", "field.123")
    client.post(f"/helpdesk/staff/ticket/{reference}/claim", follow_redirects=True)

    with app.app_context():
        manager_id = User.query.filter_by(username="ictmanager").one().id

    response = client.post(
        f"/helpdesk/staff/ticket/{reference}/assign",
        data={"staff_id": manager_id, "origin": "queue"},
        follow_redirects=True,
    )

    assert b"transferred to ICT Manager" in response.data
    assert ticket_state(app, reference) == ("in_progress", "ictmanager")


def test_a_held_task_cannot_be_taken_by_someone_else(client, app, intern):
    reference = a_ticket(client, app)
    sign_in(client, "icthelpdesk", "field.123")
    client.post(f"/helpdesk/staff/ticket/{reference}/claim", follow_redirects=True)
    sign_out(client)

    sign_in(client, "intern_ann", "field.123")
    response = client.post(f"/helpdesk/staff/ticket/{reference}/claim", follow_redirects=True)

    assert b"Ask them to return it" in response.data
    assert ticket_state(app, reference) == ("in_progress", "icthelpdesk")

    denied = client.post(f"/helpdesk/staff/ticket/{reference}/release", follow_redirects=True)
    assert b"Only the assignee or the ICT manager" in denied.data
    assert ticket_state(app, reference) == ("in_progress", "icthelpdesk")


def test_a_manager_can_take_over_a_held_task(client, app):
    reference = a_ticket(client, app)
    sign_in(client, "icthelpdesk", "field.123")
    client.post(f"/helpdesk/staff/ticket/{reference}/claim", follow_redirects=True)
    sign_out(client)

    sign_in(client, "ictmanager", "field.123")
    response = client.post(f"/helpdesk/staff/ticket/{reference}/claim", follow_redirects=True)

    assert b"You picked up" in response.data
    assert ticket_state(app, reference) == ("in_progress", "ictmanager")


def test_queue_shows_pick_return_and_transfer_controls(client, app, intern):
    reference = a_ticket(client, app)
    sign_in(client, "intern_ann", "field.123")

    unassigned_view = client.get("/helpdesk/staff").data.decode()
    assert f"/helpdesk/staff/ticket/{reference}/claim" in unassigned_view
    assert ">Pick<" in unassigned_view
    assert "Transfer to…" in unassigned_view

    client.post(f"/helpdesk/staff/ticket/{reference}/claim", follow_redirects=True)
    held_view = client.get("/helpdesk/staff").data.decode()

    assert f"/helpdesk/staff/ticket/{reference}/release" in held_view
    assert ">Return<" in held_view
    assert ">Yours<" in held_view


def test_my_tasks_filter_shows_only_what_i_hold(client, app, intern):
    mine = a_ticket(client, app, "Mine to solve")
    theirs = a_ticket(client, app, "Somebody else's")

    sign_in(client, "intern_ann", "field.123")
    client.post(f"/helpdesk/staff/ticket/{mine}/claim", follow_redirects=True)

    body = client.get("/helpdesk/staff?status=mine").data.decode()

    assert "Mine to solve" in body
    assert "Somebody else's" not in body
    assert "My tasks (1)" in body


def test_unassigned_filter_shows_the_free_pool(client, app, intern):
    taken = a_ticket(client, app, "Already taken")
    free = a_ticket(client, app, "Still free")

    sign_in(client, "intern_ann", "field.123")
    client.post(f"/helpdesk/staff/ticket/{taken}/claim", follow_redirects=True)

    body = client.get("/helpdesk/staff?status=unassigned").data.decode()

    assert "Still free" in body
    assert "Already taken" not in body


def test_every_handover_is_written_to_the_audit_trail(client, app, intern):
    reference = a_ticket(client, app)

    sign_in(client, "intern_ann", "field.123")
    client.post(f"/helpdesk/staff/ticket/{reference}/claim", follow_redirects=True)
    client.post(f"/helpdesk/staff/ticket/{reference}/release", follow_redirects=True)
    client.post(f"/helpdesk/staff/ticket/{reference}/claim", follow_redirects=True)

    with app.app_context():
        events = Ticket.query.filter_by(reference=reference).one().events
        handovers = [e for e in events if e.event_type == "assignment"]

        assert [e.message for e in handovers] == [
            "Picked up by Ann Intern.",
            "Returned to the queue by Ann Intern.",
            "Picked up by Ann Intern.",
        ]
        # Intern actions are recorded as their own role, not lumped in with officers.
        assert {e.actor_role for e in handovers} == {"intern"}


def test_a_plain_account_still_cannot_pick_tasks(client, app):
    reference = a_ticket(client, app)

    sign_in(client, "jonyango", "field.123")
    create_user(client, "plain_user")
    sign_out(client)
    sign_in(client, "plain_user", "field.123")

    response = client.post(f"/helpdesk/staff/ticket/{reference}/claim", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
    assert ticket_state(app, reference) == ("open", None)
