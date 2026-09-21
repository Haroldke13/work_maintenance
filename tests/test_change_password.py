"""Changing your own password, and the warning about the shared default."""

import pytest

from conftest import sign_in, sign_out

from accounts import MIN_PASSWORD_LENGTH
from models import User


NEW = "a-password-of-my-own"


def change(client, current="field.123", new=NEW, confirm=None):
    return client.post(
        "/account/password",
        data={
            "current_password": current,
            "new_password": new,
            "confirm_password": new if confirm is None else confirm,
        },
        follow_redirects=True,
    )


def password_works(app, username, password) -> bool:
    with app.app_context():
        return User.query.filter_by(username=username).one().check_password(password)


# --- Changing it ---------------------------------------------------------


def test_a_signed_in_account_changes_its_own_password(client, app):
    sign_in(client, "icthelpdesk", "field.123")

    response = change(client)

    assert b"Your password has been changed." in response.data
    assert password_works(app, "icthelpdesk", NEW)
    assert not password_works(app, "icthelpdesk", "field.123")


def test_the_new_password_is_what_signs_you_in_next_time(client):
    sign_in(client, "icthelpdesk", "field.123")
    change(client)
    sign_out(client)

    assert b"Invalid username or password" in sign_in(client, "icthelpdesk", "field.123").data
    assert b"Signed in as" in sign_in(client, "icthelpdesk", NEW).data


def test_changing_it_does_not_sign_you_out(client):
    sign_in(client, "icthelpdesk", "field.123")

    change(client)

    assert client.get("/maintenance").status_code == 200


@pytest.mark.parametrize("username", ["jonyango", "ictmanager", "icthelpdesk"])
def test_every_kind_of_account_can_change_its_own(client, app, username):
    sign_in(client, username, "field.123")

    change(client)

    assert password_works(app, username, NEW)


def test_a_self_registered_account_can_change_its_own_too(client, app, outbox):
    """It set its password at signup, so it must be able to move off it."""
    from test_signup_and_gate import confirmation_link, signup

    signup(client)
    client.get(confirmation_link(outbox[0]))

    response = change(client, current="portal-pass-1")

    assert b"Your password has been changed." in response.data
    assert password_works(app, "new.officer", NEW)


# --- What it refuses -----------------------------------------------------


def test_the_current_password_must_be_right(client, app):
    sign_in(client, "icthelpdesk", "field.123")

    response = change(client, current="not-my-password")

    assert b"not your current password" in response.data
    assert password_works(app, "icthelpdesk", "field.123")


def test_a_short_new_password_is_refused(client, app):
    sign_in(client, "icthelpdesk", "field.123")

    response = change(client, new="short")

    assert f"at least {MIN_PASSWORD_LENGTH} characters".encode() in response.data
    assert password_works(app, "icthelpdesk", "field.123")


def test_the_two_new_passwords_must_match(client, app):
    sign_in(client, "icthelpdesk", "field.123")

    response = change(client, new=NEW, confirm="something-else-entirely")

    assert b"do not match" in response.data
    assert password_works(app, "icthelpdesk", "field.123")


def test_the_new_password_must_actually_be_new(client, app):
    sign_in(client, "icthelpdesk", "field.123")

    response = change(client, current="field.123", new="field.123")

    assert b"must be different from the current one" in response.data


def test_signed_out_you_are_sent_to_the_sign_in(client):
    response = client.get("/account/password", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_you_cannot_change_a_password_by_posting_while_signed_out(client, app):
    response = change(client)

    assert response.status_code == 200
    assert password_works(app, "icthelpdesk", "field.123")


# --- The shared-default warning ------------------------------------------


def test_the_page_warns_while_the_account_is_on_the_shared_default(client):
    sign_in(client, "icthelpdesk", "field.123")

    page = client.get("/account/password").get_data(as_text=True)

    assert "still uses the shared starting password" in page


def test_the_warning_goes_away_once_the_password_is_their_own(client):
    sign_in(client, "icthelpdesk", "field.123")
    change(client)

    page = client.get("/account/password").get_data(as_text=True)

    assert "still uses the shared starting password" not in page


# --- Reachability --------------------------------------------------------


@pytest.mark.parametrize("path", ["/maintenance", "/admin", "/helpdesk/staff"])
def test_the_password_link_is_in_the_chrome_staff_work_in(client, path):
    sign_in(client, "jonyango", "field.123")

    page = client.get(path).get_data(as_text=True)

    assert '/account/password' in page


def test_every_shell_offers_a_way_out(client):
    """Gating the portal means sign-out has to be reachable from inside it."""
    sign_in(client, "jonyango", "field.123")

    for path in ("/maintenance", "/admin", "/helpdesk/staff"):
        page = client.get(path).get_data(as_text=True)
        assert 'action="/logout"' in page, path
