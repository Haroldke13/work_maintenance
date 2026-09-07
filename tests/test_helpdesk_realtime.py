"""Socket.IO behaviour: the help desk must learn about tickets without refreshing."""

from conftest import sign_in, sign_out, submit_complaint

from HELP_DESK.models import Ticket
from models import User


def events_named(received, name):
    return [event for event in received if event["name"] == name]


def latest_ticket(app):
    with app.app_context():
        return Ticket.query.order_by(Ticket.id.desc()).first()


def test_dashboard_room_is_closed_to_anonymous_visitors(app, client, sio):
    socket = sio()
    reply = socket.emit("join_dashboard", {}, callback=True)

    assert reply == {"joined": False, "reason": "not_authorised"}


def test_staff_join_dashboard_and_receive_stats(app, client, sio):
    sign_in(client)
    socket = sio()

    reply = socket.emit("join_dashboard", {}, callback=True)

    assert reply["joined"] is True
    assert reply["stats"]["open"] >= 1
    assert "overdue" in reply["stats"]


def test_new_complaint_is_pushed_to_the_help_desk(app, client, sio):
    sign_in(client)
    socket = sio()
    socket.emit("join_dashboard", {}, callback=True)
    socket.get_received()

    submit_complaint(
        client,
        category_key="virus_malware",
        subject="Suspicious pop-ups on my laptop",
        description="Pop-ups started after I opened an email attachment.",
    )

    created = events_named(socket.get_received(), "ticket:created")

    assert len(created) == 1
    payload = created[0]["args"][0]
    assert payload["subject"] == "Suspicious pop-ups on my laptop"
    assert payload["priority"] == "urgent"
    assert payload["status"] == "open"


def test_reporter_self_resolution_notifies_the_help_desk(app, client, sio):
    submit_complaint(client)
    ticket = latest_ticket(app)

    sign_in(client)
    socket = sio()
    socket.emit("join_dashboard", {}, callback=True)
    socket.get_received()

    client.post(
        f"/helpdesk/ticket/{ticket.reference}/status?token={ticket.access_token}",
        data={"status": "resolved", "message": "A restart fixed it."},
    )

    resolved = events_named(socket.get_received(), "ticket:resolved")

    assert len(resolved) == 1
    payload = resolved[0]["args"][0]
    assert payload["reference"] == ticket.reference
    assert payload["self_resolved"] is True
    assert payload["resolved_by"] == "Jane Reporter"
    assert payload["minutes_to_resolve"] is not None


def test_staff_resolution_is_not_flagged_as_self_resolved(app, client, sio):
    submit_complaint(client)
    reference = latest_ticket(app).reference

    sign_in(client)
    socket = sio()
    socket.emit("join_dashboard", {}, callback=True)
    socket.get_received()

    client.post(
        f"/helpdesk/staff/ticket/{reference}/status",
        data={"status": "resolved", "message": "Cleared the print queue."},
    )

    payload = events_named(socket.get_received(), "ticket:resolved")[0]["args"][0]

    assert payload["self_resolved"] is False
    assert payload["resolved_by"] == "ICT Help Desk Officer"


def test_stats_are_pushed_after_every_state_change(app, client, sio):
    submit_complaint(client)
    reference = latest_ticket(app).reference

    sign_in(client)
    socket = sio()
    socket.emit("join_dashboard", {}, callback=True)
    socket.get_received()

    client.post(
        f"/helpdesk/staff/ticket/{reference}/status",
        data={"status": "resolved", "message": "Cleared the print queue."},
    )

    stats = events_named(socket.get_received(), "stats")

    assert stats, "dashboard counters should refresh without a page reload"
    assert stats[-1]["args"][0]["resolved"] >= 1


def test_ticket_room_requires_the_tracking_token(app, client, sio):
    submit_complaint(client)
    ticket = latest_ticket(app)
    socket = sio()

    assert socket.emit(
        "join_ticket", {"reference": ticket.reference, "token": "wrong"}, callback=True
    ) == {"joined": False, "reason": "not_authorised"}

    assert socket.emit("join_ticket", {"reference": "HD-2026-9999"}, callback=True) == {
        "joined": False,
        "reason": "not_found",
    }

    reply = socket.emit(
        "join_ticket", {"reference": ticket.reference, "token": ticket.access_token}, callback=True
    )
    assert reply["joined"] is True
    assert reply["ticket"]["reference"] == ticket.reference


def test_reporter_watching_a_ticket_sees_the_staff_reply_live(app, client, sio):
    submit_complaint(client)
    ticket = latest_ticket(app)

    watcher = sio()
    watcher.emit(
        "join_ticket", {"reference": ticket.reference, "token": ticket.access_token}, callback=True
    )
    watcher.get_received()

    sign_in(client)
    client.post(
        f"/helpdesk/staff/ticket/{ticket.reference}/comment",
        data={"message": "An officer is on the way to your desk."},
    )

    comments = events_named(watcher.get_received(), "ticket:comment")

    assert len(comments) == 1
    event = comments[0]["args"][0]["event"]
    assert event["message"] == "An officer is on the way to your desk."
    assert event["actor_role"] == "officer"
