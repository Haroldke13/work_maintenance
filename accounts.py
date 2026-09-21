"""Self-service registration for the ICT portal.

Anyone at the Authority can open an account themselves: email, password,
confirm password. The address is not taken on trust — the account is created
unconfirmed and cannot sign in until the link mailed to that address is
clicked. That link is a signed, expiring token rather than a stored column, so
there is nothing to clean up and nothing to leak from the database.

A self-registered account gets no rights beyond a signed-in user's: no
`is_admin`, no `helpdesk_role`. An administrator grants those afterwards from
the console.
"""

import re

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from auth import current_user, landing_page_for, login_user
from extensions import db
from mailer import best_effort, send_email
from models import User
from notifications import email_new_account


# Long enough to be worth typing, short enough that nobody reaches for a
# sticky note. Staff-set passwords keep their own, laxer rule in admin_users.
MIN_PASSWORD_LENGTH = 8

# Deliberately loose: the confirmation email is what actually proves the
# address, so this only catches typos that could never be delivered.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Namespaces the signature, so a confirmation token cannot be replayed against
# some other feature that signs with the same secret key.
CONFIRM_SALT = "account-email-confirmation"


def is_valid_email(address: str) -> bool:
    return bool(EMAIL_PATTERN.match(address or ""))


def normalized_email(address: str) -> str:
    return (address or "").strip().lower()


def accounts_with_email(address: str) -> list[User]:
    """Every account on an address, matched case-insensitively.

    A list rather than one row because the address is not unique: the seeded
    help desk manager and officer deliberately share the shared ICT inbox, and
    a unique constraint would break that. Uniqueness is enforced where it
    actually matters — signup refuses an address that is already spoken for.
    """
    address = normalized_email(address)
    if not address:
        return []
    return User.query.filter(db.func.lower(User.email) == address).all()


def account_with_email(address: str) -> User | None:
    """The one account on an address, or None if none — or if it is shared."""
    matches = accounts_with_email(address)
    return matches[0] if len(matches) == 1 else None


def find_account(identifier: str) -> User | None:
    """Sign-in accepts either identity: the username staff know, or the email.

    Self-registered accounts never chose a username, so the address they typed
    into the signup form has to work at the sign-in form too.

    A shared address identifies nobody, so it resolves to None and those
    accounts sign in by username — better than silently picking whichever row
    the database happened to return first.
    """
    identifier = (identifier or "").strip()
    if not identifier:
        return None

    user = User.query.filter_by(username=identifier).first()
    return user if user else account_with_email(identifier)


def username_for(email: str) -> str:
    """A login name derived from the address, since signup does not ask for one.

    The local part, stripped to what the username column and the URLs around it
    handle, then numbered if it is taken.
    """
    base = re.sub(r"[^a-z0-9._-]", "", normalized_email(email).split("@")[0])[:60]
    base = base.strip("._-") or "user"

    candidate, suffix = base, 1
    while User.query.filter_by(username=candidate).first() is not None:
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


# --------------------------------------------------------------------------- #
# Confirmation tokens
# --------------------------------------------------------------------------- #

def serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=CONFIRM_SALT)


def confirmation_token(user: User) -> str:
    # The address is signed alongside the id, so a token stops working the
    # moment the account's address is changed to a different one.
    return serializer().dumps({"id": user.id, "email": normalized_email(user.email)})


def account_from_token(token: str) -> User | None:
    """The account a valid, unexpired token names — or None."""
    max_age = current_app.config["EMAIL_CONFIRM_MAX_AGE"]
    try:
        payload = serializer().loads(token, max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None

    if not isinstance(payload, dict):
        return None

    user = db.session.get(User, payload.get("id"))
    if user is None or normalized_email(user.email) != payload.get("email"):
        return None
    return user


@best_effort
def email_confirmation_link(user: User) -> bool:
    """The one email that is addressed to a single person, not the notify list."""
    link = url_for("confirm_email", token=confirmation_token(user), _external=True)
    hours = current_app.config["EMAIL_CONFIRM_MAX_AGE"] // 3600

    body = "\n".join(
        [
            f"Hello {user.display_name},",
            "",
            "An account was opened for this address on the PBO Regulatory",
            "Authority ICT portal. Confirm the address to activate it:",
            "",
            link,
            "",
            f"The link expires in {hours} hours. Your sign-in name is {user.username};",
            "you can sign in with either that or this email address.",
            "",
            "If you did not open this account, ignore this email — an",
            "unconfirmed account cannot sign in.",
        ]
    )

    return send_email(
        subject="Confirm your PBORA ICT portal account",
        body=body,
        recipients=[user.email],
    )


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

def register_account_routes(app) -> None:

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if current_user() is not None:
            flash("You are already signed in.", "info")
            return redirect(url_for("index"))

        form_data = {"email": ""}

        if request.method == "POST":
            form_data["email"] = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            errors = validate_signup(form_data["email"], password, confirm)

            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                user = create_self_registered_account(form_data["email"], password)
                email_confirmation_link(user)
                flash(
                    f"Account created. We sent a confirmation link to {user.email} — "
                    "click it to activate the account, then sign in.",
                    "success",
                )
                return redirect(url_for("login"))

        return render_template(
            "signup.html", form_data=form_data, min_password_length=MIN_PASSWORD_LENGTH
        )

    @app.route("/confirm/<token>")
    def confirm_email(token: str):
        user = account_from_token(token)

        if user is None:
            flash(
                "That confirmation link is invalid or has expired. "
                "Request a new one below.",
                "danger",
            )
            return redirect(url_for("resend_confirmation"))

        if not user.awaiting_email_confirmation:
            flash("That address is already confirmed — you can sign in.", "info")
            return redirect(url_for("login"))

        user.confirm_email()
        db.session.commit()
        # Only now is the account real: an unconfirmed one cannot sign in and
        # is as likely to be a mistyped address as a person.
        email_new_account(user, "self-service signup")

        # The link was just proved to come from their inbox, so there is no
        # reason to make them type the password they set minutes ago.
        login_user(user)
        flash(f"Email confirmed. Welcome, {user.display_name}.", "success")
        return redirect(url_for("index"))

    @app.route("/account/password", methods=["GET", "POST"])
    def change_password():
        """Any signed-in account changes its own password.

        Every account is seeded with the same `field.123`, so this is the one
        way a person can stop sharing a password with the rest of the office.
        The administrator's reset in the console stays as it was — that is for
        an account whose holder cannot get in at all.
        """
        user = current_user()
        if user is None:
            flash("Sign in to change your password.", "warning")
            return redirect(url_for("login", next=request.full_path))

        if request.method == "POST":
            current = request.form.get("current_password", "")
            new = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")
            errors = validate_password_change(user, current, new, confirm)

            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                user.set_password(new)
                db.session.commit()
                # The session keys off the account id, not the password, so
                # they stay signed in — no reason to make them prove it twice.
                flash("Your password has been changed.", "success")
                return redirect(landing_page_for(user))

        return render_template(
            "change_password.html",
            account=user,
            min_password_length=MIN_PASSWORD_LENGTH,
            using_shared_default=uses_shared_default(user),
        )

    @app.route("/confirm/resend", methods=["GET", "POST"])
    def resend_confirmation():
        email = request.values.get("email", "").strip()

        if request.method == "POST":
            user = account_with_email(email)
            if user is not None and user.awaiting_email_confirmation:
                email_confirmation_link(user)
            # Always the same answer: whether an address holds an account is
            # not something an unauthenticated form should report back.
            flash(
                "If that address has an unconfirmed account, a new "
                "confirmation link is on its way.",
                "info",
            )
            return redirect(url_for("login"))

        return render_template("confirm_resend.html", email=email)


def validate_signup(email: str, password: str, confirm: str) -> list[str]:
    errors = []

    if not email:
        errors.append("Email address is required.")
    elif not is_valid_email(email):
        errors.append("Enter a valid email address.")
    elif accounts_with_email(email):
        errors.append(
            "An account already exists for that address. Sign in, or request a "
            "new confirmation link."
        )

    if not password:
        errors.append("Password is required.")
    elif len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"A password must be at least {MIN_PASSWORD_LENGTH} characters.")

    if not confirm:
        errors.append("Confirm your password.")
    elif password and password != confirm:
        errors.append("The two passwords do not match.")

    return errors


def validate_password_change(user: User, current: str, new: str, confirm: str) -> list[str]:
    errors = []

    if not current:
        errors.append("Enter your current password.")
    elif not user.check_password(current):
        errors.append("That is not your current password.")

    if not new:
        errors.append("Enter a new password.")
    elif len(new) < MIN_PASSWORD_LENGTH:
        errors.append(f"A password must be at least {MIN_PASSWORD_LENGTH} characters.")
    elif new == current:
        errors.append("The new password must be different from the current one.")

    if not confirm:
        errors.append("Confirm the new password.")
    elif new and new != confirm:
        errors.append("The two new passwords do not match.")

    return errors


def uses_shared_default(user: User) -> bool:
    """Whether this account still holds a password the whole office knows.

    Every seeded account starts on the same configured password, so this is
    what the page warns about rather than any judgement of password strength.
    """
    defaults = {
        current_app.config.get(key)
        for key in (
            "DEFAULT_USER_PASSWORD",
            "ADMIN_PASSWORD",
            "HELPDESK_MANAGER_PASSWORD",
            "HELPDESK_OFFICER_PASSWORD",
        )
    }
    return any(password and user.check_password(password) for password in defaults)


def create_self_registered_account(email: str, password: str) -> User:
    """An unconfirmed account with no rights. `created_by` records where it came from."""
    email = normalized_email(email)
    user = User(
        username=username_for(email),
        email=email,
        is_admin=False,
        helpdesk_role=None,
        is_active=True,
        receives_notifications=True,
        self_registered=True,
        created_by="self-signup",
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user
