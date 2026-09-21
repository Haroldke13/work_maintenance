"""Self-service signup, the confirmation email, and the gate around the portal."""

import re

import pytest

from conftest import sign_in, sign_out

from accounts import MIN_PASSWORD_LENGTH, confirmation_token
from extensions import db
from models import User


def signup(client, email="new.officer@pbora.go.ke", password="portal-pass-1", confirm=None):
    return client.post(
        "/signup",
        data={
            "email": email,
            "password": password,
            "confirm_password": password if confirm is None else confirm,
        },
        follow_redirects=True,
    )


def confirmation_link(message) -> str:
    """The /confirm/<token> URL out of the email body."""
    match = re.search(r"https?://\S+/confirm/\S+", message.get_content())
    assert match, message.get_content()
    return match.group(0)


def account(app, email="new.officer@pbora.go.ke") -> User:
    with app.app_context():
        return User.query.filter_by(email=email).one()


# --- The gate ------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/", "/maintenance", "/submissions", "/assets", "/scripts", "/table/1", "/admin"],
)
def test_the_portal_is_closed_to_anyone_signed_out(client, path):
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


@pytest.mark.parametrize(
    "path", ["/login", "/signup", "/confirm/resend", "/helpdesk/", "/helpdesk/track"]
)
def test_the_door_and_the_help_desk_intake_stay_open(client, path):
    assert client.get(path).status_code == 200


def test_signing_in_opens_the_homepage(client):
    sign_in(client)

    response = client.get("/", follow_redirects=True)

    assert response.status_code == 200
    assert b"Computer Maintenance Report (NGOB/ICT/104b)" in response.data


def test_the_gate_sends_you_back_to_where_you_were_headed(client):
    response = client.get("/submissions", follow_redirects=False)

    # `request.full_path` is what the gate remembers, trailing "?" and all.
    assert "next=/submissions" in response.headers["Location"]


def test_the_sign_in_form_will_not_bounce_you_off_site(client):
    """`next` reaches the form on every gated request, so it must stay local."""
    response = client.post(
        "/login",
        data={"username": "icthelpdesk", "password": "field.123",
              "next": "https://evil.test/steal"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "evil.test" not in response.headers["Location"]


def test_an_unknown_url_is_still_a_404_and_not_a_redirect(client):
    assert client.get("/no-such-page").status_code == 404


# --- Signing up ----------------------------------------------------------


def test_signup_creates_an_unconfirmed_account_with_no_rights(client, app, outbox):
    response = signup(client)

    assert response.status_code == 200
    assert b"confirmation link" in response.data

    user = account(app)
    assert user.self_registered is True
    assert user.awaiting_email_confirmation is True
    assert user.may_sign_in is False
    assert user.is_admin is False
    assert user.helpdesk_role is None
    assert user.created_by == "self-signup"
    # A username is derived, since signup never asks for one.
    assert user.username == "new.officer"


def test_the_confirmation_email_goes_only_to_the_address_that_signed_up(client, outbox):
    signup(client)

    assert len(outbox) == 1
    message = outbox[0]

    assert message["To"] == "new.officer@pbora.go.ke"
    assert "Confirm your PBORA ICT portal account" in message["Subject"]
    assert "/confirm/" in message.get_content()


def test_an_unconfirmed_account_cannot_sign_in(client, app, outbox):
    signup(client)

    response = sign_in(client, "new.officer@pbora.go.ke", "portal-pass-1")

    assert b"Confirm your email address before signing in" in response.data
    # Still outside: the homepage remains shut.
    assert client.get("/", follow_redirects=False).status_code == 302


def test_clicking_the_link_confirms_the_account_and_signs_it_in(client, app, outbox):
    signup(client)
    link = confirmation_link(outbox[0])

    response = client.get(link, follow_redirects=True)

    assert response.status_code == 200
    assert b"Email confirmed" in response.data

    user = account(app)
    assert user.awaiting_email_confirmation is False
    assert user.email_confirmed_at is not None
    # And the portal is now open to them.
    assert client.get("/maintenance").status_code == 200


def test_a_confirmed_account_signs_in_with_either_its_email_or_its_username(
    client, app, outbox
):
    signup(client)
    client.get(confirmation_link(outbox[0]))
    sign_out(client)

    by_email = sign_in(client, "new.officer@pbora.go.ke", "portal-pass-1")
    assert b"Signed in as" in by_email.data
    sign_out(client)

    by_username = sign_in(client, "new.officer", "portal-pass-1")
    assert b"Signed in as" in by_username.data


def test_a_second_click_on_a_spent_link_is_harmless(client, outbox):
    signup(client)
    link = confirmation_link(outbox[0])
    client.get(link)
    sign_out(client)

    response = client.get(link, follow_redirects=True)

    assert b"already confirmed" in response.data


def test_a_tampered_or_expired_link_is_refused(client, app, outbox):
    signup(client)
    link = confirmation_link(outbox[0])

    tampered = client.get(link[:-4] + "xxxx", follow_redirects=True)
    assert b"invalid or has expired" in tampered.data

    # The same, good token, once its lifetime has run out.
    app.config["EMAIL_CONFIRM_MAX_AGE"] = -1
    expired = client.get(link, follow_redirects=True)
    assert b"invalid or has expired" in expired.data

    with app.app_context():
        assert User.query.filter_by(email="new.officer@pbora.go.ke").one().may_sign_in is False


def test_a_token_dies_when_the_account_address_changes(client, app, outbox):
    """The address is signed into the token, so it cannot confirm a new one."""
    signup(client)
    link = confirmation_link(outbox[0])

    with app.app_context():
        user = User.query.filter_by(email="new.officer@pbora.go.ke").one()
        user.email = "someone.else@pbora.go.ke"
        db.session.commit()

    response = client.get(link, follow_redirects=True)

    assert b"invalid or has expired" in response.data


# --- What signup refuses -------------------------------------------------


def test_the_two_passwords_must_match(client, app, outbox):
    response = signup(client, password="portal-pass-1", confirm="portal-pass-2")

    assert b"do not match" in response.data
    with app.app_context():
        assert User.query.filter_by(email="new.officer@pbora.go.ke").first() is None
    assert outbox == []


def test_a_short_password_is_refused(client, app):
    response = signup(client, password="short")

    assert f"at least {MIN_PASSWORD_LENGTH} characters".encode() in response.data
    with app.app_context():
        assert User.query.filter_by(email="new.officer@pbora.go.ke").first() is None


@pytest.mark.parametrize("email", ["", "not-an-email", "no@domain", "@pbora.go.ke"])
def test_an_unusable_address_is_refused(client, app, email):
    response = signup(client, email=email)

    assert b"valid email address" in response.data or b"required" in response.data
    with app.app_context():
        assert User.query.filter_by(email=email).first() is None


def test_an_address_that_already_holds_an_account_is_refused(client, app, outbox):
    signup(client)
    outbox.clear()

    response = signup(client, email="NEW.Officer@PBORA.go.ke", password="another-pass-9")

    assert b"already exists for that address" in response.data
    assert outbox == []
    with app.app_context():
        assert User.query.filter(
            db.func.lower(User.email) == "new.officer@pbora.go.ke"
        ).count() == 1


def test_signing_up_grants_nothing_the_admin_console_needs(client, app, outbox):
    signup(client)
    client.get(confirmation_link(outbox[0]))

    assert client.get("/admin", follow_redirects=False).status_code == 302
    assert client.get("/helpdesk/staff", follow_redirects=False).status_code == 302


# --- Resending -----------------------------------------------------------


def test_resend_issues_a_fresh_working_link(client, app, outbox):
    signup(client)
    outbox.clear()

    response = client.post(
        "/confirm/resend", data={"email": "new.officer@pbora.go.ke"}, follow_redirects=True
    )

    assert b"on its way" in response.data
    assert len(outbox) == 1

    client.get(confirmation_link(outbox[0]), follow_redirects=True)
    assert account(app).awaiting_email_confirmation is False


def test_resend_does_not_reveal_whether_an_address_has_an_account(client, outbox):
    unknown = client.post(
        "/confirm/resend", data={"email": "nobody@pbora.go.ke"}, follow_redirects=True
    )

    assert b"on its way" in unknown.data
    assert outbox == []


def test_resend_stays_quiet_for_an_account_that_is_already_confirmed(client, outbox):
    signup(client)
    client.get(confirmation_link(outbox[0]))
    sign_out(client)
    outbox.clear()

    client.post(
        "/confirm/resend", data={"email": "new.officer@pbora.go.ke"}, follow_redirects=True
    )

    assert outbox == []


# --- Accounts staff create -----------------------------------------------


def test_a_staff_created_account_needs_no_confirmation(client, app):
    """Nobody has to prove an address the administrator typed in themselves."""
    sign_in(client, "jonyango", "field.123")
    client.post(
        "/admin/users/new",
        data={"username": "desk_three", "email": "desk.three@pbora.go.ke",
              "helpdesk_role": "officer"},
        follow_redirects=True,
    )

    with app.app_context():
        created = User.query.filter_by(username="desk_three").one()
        assert created.self_registered is False
        assert created.may_sign_in is True

    sign_out(client)
    assert b"Signed in as" in sign_in(client, "desk_three", "field.123").data


def test_a_deactivated_account_loses_the_session_it_already_holds(client, app):
    sign_in(client)
    assert client.get("/maintenance").status_code == 200

    with app.app_context():
        user = User.query.filter_by(username="icthelpdesk").one()
        user.is_active = False
        db.session.commit()

    assert client.get("/maintenance", follow_redirects=False).status_code == 302


# --- Derived usernames ---------------------------------------------------


def test_two_addresses_with_the_same_local_part_get_distinct_usernames(client, app):
    signup(client, email="j.onyango@pbora.go.ke", password="portal-pass-1")
    signup(client, email="j.onyango@example.org", password="portal-pass-1")

    with app.app_context():
        first = User.query.filter_by(email="j.onyango@pbora.go.ke").one()
        second = User.query.filter_by(email="j.onyango@example.org").one()

        assert first.username == "j.onyango"
        assert second.username == "j.onyango2"


def test_a_token_names_the_account_it_was_cut_for(client, app, outbox):
    signup(client)

    with app.app_context():
        user = User.query.filter_by(email="new.officer@pbora.go.ke").one()
        token = confirmation_token(user)

    assert client.get(f"/confirm/{token}", follow_redirects=True).status_code == 200
    assert account(app).awaiting_email_confirmation is False


# --- A shared address ----------------------------------------------------


def test_a_shared_address_identifies_nobody_at_sign_in(client, app):
    """The seeded manager and officer both sit on the shared ICT inbox."""
    with app.app_context():
        shared = User.query.filter_by(email="ictsupport@pbora.go.ke").all()
        assert len(shared) > 1, "this test needs the shared-inbox accounts"

    by_shared_email = sign_in(client, "ictsupport@pbora.go.ke", "field.123")

    assert b"Invalid username or password" in by_shared_email.data
    # Each of them still signs in by the username that is theirs alone.
    assert b"Signed in as" in sign_in(client, "icthelpdesk", "field.123").data


def test_signup_still_refuses_an_address_that_is_shared(client, app, outbox):
    response = signup(client, email="ictsupport@pbora.go.ke", password="portal-pass-1")

    assert b"already exists for that address" in response.data
    assert outbox == []


# --- ICT is told about new accounts --------------------------------------


def test_ict_is_emailed_when_a_signup_confirms(client, app, outbox):
    signup(client)
    link = confirmation_link(outbox[0])
    outbox.clear()

    client.get(link)

    assert len(outbox) == 1
    message = outbox[0]

    assert "jonyango@pbora.go.ke" in message["To"]
    assert message["Subject"] == "[ICT Portal] New account: new.officer"
    body = message.get_content()
    assert "new.officer@pbora.go.ke" in body
    assert "self-service signup" in body


def test_an_unconfirmed_signup_does_not_alert_ict_yet(client, outbox):
    """A typo'd address must not look like a new member of staff."""
    signup(client)

    assert len(outbox) == 1
    assert outbox[0]["Subject"].startswith("Confirm your")


def test_ict_is_emailed_when_an_admin_creates_an_account(client, outbox):
    sign_in(client, "jonyango", "field.123")
    outbox.clear()

    client.post(
        "/admin/users/new",
        data={"username": "desk_four", "email": "desk.four@pbora.go.ke"},
        follow_redirects=True,
    )

    assert len(outbox) == 1
    assert outbox[0]["Subject"] == "[ICT Portal] New account: desk_four"
    assert "created by jonyango" in outbox[0].get_content()


def test_the_new_account_alert_does_not_go_to_every_user(client, app, outbox):
    """Who holds an account is ICT's business, not the whole notify list."""
    with app.app_context():
        bystander = User(username="bystander", email="bystander@pbora.go.ke",
                         receives_notifications=True)
        bystander.set_password("field.123")
        db.session.add(bystander)
        db.session.commit()

    signup(client)
    link = confirmation_link(outbox[0])
    outbox.clear()
    client.get(link)

    assert "bystander@pbora.go.ke" not in outbox[0]["To"]
