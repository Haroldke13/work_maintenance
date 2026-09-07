"""Administrator console: adding accounts and assigning rights."""

from conftest import create_user, sign_in, sign_out

from extensions import db
from models import User


def as_admin(client):
    return sign_in(client, "jonyango", "field.123")


def fetch(app, username):
    with app.app_context():
        return User.query.filter_by(username=username).one()


# --------------------------------------------------------------------------- #
# Access
# --------------------------------------------------------------------------- #

def test_every_admin_page_needs_administrator_rights(client, app):
    pages = ["/admin", "/admin/users", "/admin/users/new"]

    for page in pages:
        response = client.get(page, follow_redirects=False)
        assert response.status_code == 302, page
        assert "/login" in response.headers["Location"], page

    # A help desk officer is not an administrator.
    sign_in(client, "icthelpdesk", "field.123")
    for page in pages:
        assert client.get(page, follow_redirects=False).status_code == 302, page

    sign_out(client)
    as_admin(client)
    for page in pages:
        assert client.get(page).status_code == 200, page


# --------------------------------------------------------------------------- #
# Creating accounts with rights
# --------------------------------------------------------------------------- #

def test_creation_form_offers_every_role_and_privilege(client):
    as_admin(client)

    body = client.get("/admin/users/new").data.decode()

    assert 'name="is_admin"' in body
    assert 'name="helpdesk_role"' in body
    assert 'name="receives_notifications"' in body
    for label in ["ICT intern", "Help desk officer", "ICT manager"]:
        assert label in body


def test_rights_are_assigned_during_creation(client, app):
    as_admin(client)

    create_user(
        client,
        "grace.admin",
        full_name="Grace Admin",
        email="grace@pbora.go.ke",
        is_admin="on",
        helpdesk_role="manager",
        receives_notifications="on",
    )

    user = fetch(app, "grace.admin")
    assert user.is_admin is True
    assert user.helpdesk_role == "manager"
    assert user.is_manager is True
    assert user.receives_notifications is True
    assert user.email == "grace@pbora.go.ke"
    assert user.created_by == "jonyango"
    assert user.check_password("field.123")


def test_an_account_can_be_created_with_no_rights_at_all(client, app):
    as_admin(client)

    create_user(client, "plain.user")

    user = fetch(app, "plain.user")
    assert user.is_admin is False
    assert user.helpdesk_role is None
    assert user.is_helpdesk_staff is False


def test_an_intern_created_here_can_work_the_queue(client, app):
    as_admin(client)
    create_user(client, "new.intern", full_name="New Intern", helpdesk_role="intern")
    sign_out(client)

    landing = sign_in(client, "new.intern", "field.123")

    assert b"Help Desk Dashboard" in landing.data
    assert client.get("/helpdesk/staff").status_code == 200
    # Still not an administrator.
    assert client.get("/admin", follow_redirects=False).status_code == 302


def test_a_password_can_be_set_at_creation(client, app):
    as_admin(client)

    create_user(client, "custom.pass", password="opensesame")
    sign_out(client)

    assert b"Sign In" in sign_in(client, "custom.pass", "field.123").data
    assert b"Admin Dashboard" not in sign_in(client, "custom.pass", "field.123").data
    assert fetch(app, "custom.pass").check_password("opensesame")


def test_creation_rejects_bad_input(client, app):
    as_admin(client)

    assert b"Username is required" in create_user(client, "").data
    assert b"valid help desk role" in create_user(client, "x1", helpdesk_role="wizard").data
    assert b"valid email address" in create_user(client, "x2", email="not-an-email").data
    assert b"at least 6 characters" in create_user(client, "x3", password="abc").data
    assert b"already exists" in create_user(client, "jonyango").data

    with app.app_context():
        for username in ("x1", "x2", "x3"):
            assert User.query.filter_by(username=username).first() is None


# --------------------------------------------------------------------------- #
# Changing rights afterwards
# --------------------------------------------------------------------------- #

def test_rights_can_be_changed_after_creation(client, app):
    as_admin(client)
    create_user(client, "moving.up", full_name="Moving Up")
    user_id = fetch(app, "moving.up").id

    client.post(
        f"/admin/users/{user_id}",
        data={"full_name": "Moving Up", "helpdesk_role": "officer", "receives_notifications": "on"},
        follow_redirects=True,
    )
    assert fetch(app, "moving.up").helpdesk_role == "officer"

    client.post(
        f"/admin/users/{user_id}",
        data={"full_name": "Moving Up", "is_admin": "on", "helpdesk_role": "manager"},
        follow_redirects=True,
    )
    upgraded = fetch(app, "moving.up")
    assert upgraded.is_admin is True
    assert upgraded.helpdesk_role == "manager"

    # And rights can be taken away again.
    client.post(f"/admin/users/{user_id}", data={"full_name": "Moving Up"}, follow_redirects=True)
    stripped = fetch(app, "moving.up")
    assert stripped.is_admin is False
    assert stripped.helpdesk_role is None


def test_editing_never_renames_the_account(client, app):
    as_admin(client)
    create_user(client, "fixed.name")
    user_id = fetch(app, "fixed.name").id

    client.post(
        f"/admin/users/{user_id}",
        data={"username": "somebody.else", "helpdesk_role": "officer"},
        follow_redirects=True,
    )

    assert fetch(app, "fixed.name").helpdesk_role == "officer"
    with app.app_context():
        assert User.query.filter_by(username="somebody.else").first() is None


def test_password_can_be_reset_to_the_default_or_a_new_one(client, app):
    as_admin(client)
    create_user(client, "forgetful", password="originalpass")
    user_id = fetch(app, "forgetful").id

    client.post(f"/admin/users/{user_id}/password", data={"password": ""}, follow_redirects=True)
    assert fetch(app, "forgetful").check_password("field.123")

    client.post(f"/admin/users/{user_id}/password", data={"password": "brandnewpass"},
                follow_redirects=True)
    assert fetch(app, "forgetful").check_password("brandnewpass")

    short = client.post(f"/admin/users/{user_id}/password", data={"password": "abc"},
                        follow_redirects=True)
    assert b"at least 6 characters" in short.data
    assert fetch(app, "forgetful").check_password("brandnewpass")


def test_an_account_can_be_deactivated_and_reactivated(client, app):
    as_admin(client)
    create_user(client, "on.leave")
    user_id = fetch(app, "on.leave").id

    client.post(f"/admin/users/{user_id}/status", data={"activate": "0"}, follow_redirects=True)
    assert fetch(app, "on.leave").is_active is False

    sign_out(client)
    assert b"Invalid username or password" in sign_in(client, "on.leave", "field.123").data

    as_admin(client)
    client.post(f"/admin/users/{user_id}/status", data={"activate": "1"}, follow_redirects=True)
    assert fetch(app, "on.leave").is_active is True


# --------------------------------------------------------------------------- #
# Lock-out guardrails
# --------------------------------------------------------------------------- #

def test_an_admin_cannot_remove_their_own_administrator_rights(client, app):
    as_admin(client)
    admin_id = fetch(app, "jonyango").id

    response = client.post(
        f"/admin/users/{admin_id}",
        data={"full_name": "ICT Administrator", "helpdesk_role": "manager"},
        follow_redirects=True,
    )

    assert b"cannot remove your own administrator rights" in response.data
    assert fetch(app, "jonyango").is_admin is True


def test_an_admin_cannot_deactivate_themselves(client, app):
    as_admin(client)
    admin_id = fetch(app, "jonyango").id

    response = client.post(
        f"/admin/users/{admin_id}/status", data={"activate": "0"}, follow_redirects=True
    )

    assert b"cannot deactivate your own account" in response.data
    assert fetch(app, "jonyango").is_active is True


def test_the_last_administrator_cannot_be_stripped_or_deactivated(client, app):
    as_admin(client)
    create_user(client, "second.admin", is_admin="on")
    second_id = fetch(app, "second.admin").id

    # With two admins, demoting the other one is fine.
    client.post(f"/admin/users/{second_id}", data={}, follow_redirects=True)
    assert fetch(app, "second.admin").is_admin is False

    # Now make them the only admin and try again as them.
    client.post(f"/admin/users/{second_id}", data={"is_admin": "on"}, follow_redirects=True)
    with app.app_context():
        admin = User.query.filter_by(username="jonyango").one()
        admin.is_admin = False
        db.session.commit()

    sign_out(client)
    sign_in(client, "second.admin", "field.123")

    demote = client.post(f"/admin/users/{second_id}", data={}, follow_redirects=True)
    assert b"cannot remove your own administrator rights" in demote.data
    assert fetch(app, "second.admin").is_admin is True


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #

def test_user_list_filters_and_searches(client, app):
    as_admin(client)
    create_user(client, "search.me", full_name="Search Me", helpdesk_role="officer")
    create_user(client, "nobody.special")

    admins = client.get("/admin/users?rights=admin").data.decode()
    assert "jonyango" in admins
    assert "nobody.special" not in admins

    helpdesk = client.get("/admin/users?rights=helpdesk").data.decode()
    assert "search.me" in helpdesk
    assert "nobody.special" not in helpdesk

    none = client.get("/admin/users?rights=none").data.decode()
    assert "nobody.special" in none
    assert "search.me" not in none

    found = client.get("/admin/users?q=Search+Me").data.decode()
    assert "search.me" in found
    assert "nobody.special" not in found

    empty = client.get("/admin/users?q=zzzznothing").data.decode()
    assert "No accounts match this view" in empty


def test_console_links_to_user_management(client):
    as_admin(client)

    body = client.get("/admin").data.decode()

    assert "/admin/users/new" in body
    assert "/admin/users" in body
    assert "Add User" in body
