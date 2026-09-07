"""User management for the administrator: add accounts and assign rights.

Rights are two separate things and are kept that way:

* ``is_admin``      — the administrator console (this module, and all records).
* ``helpdesk_role`` — how the account works the help desk queue.

An account can hold either, both, or neither. The guardrails below exist so an
administrator cannot lock themselves — or everyone — out of the console.
"""

from flask import flash, redirect, render_template, request, url_for

from auth import admin_required, current_admin
from extensions import db
from models import HELPDESK_ROLES, MaintenanceReport, User


def register_admin_user_routes(app) -> None:

    @app.route("/admin/users")
    @admin_required
    def admin_users():
        search = request.args.get("q", "").strip()
        rights = request.args.get("rights", "all")

        query = User.query
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                db.or_(
                    User.username.ilike(pattern),
                    User.full_name.ilike(pattern),
                    User.email.ilike(pattern),
                )
            )
        if rights == "admin":
            query = query.filter(User.is_admin.is_(True))
        elif rights == "helpdesk":
            query = query.filter(User.helpdesk_role.isnot(None))
        elif rights == "none":
            query = query.filter(User.helpdesk_role.is_(None), User.is_admin.is_(False))
        elif rights == "inactive":
            query = query.filter(User.is_active.is_(False))

        return render_template(
            "admin_users.html",
            users=query.order_by(User.username).all(),
            total=User.query.count(),
            helpdesk_roles=HELPDESK_ROLES,
            search=search,
            rights=rights,
        )

    @app.route("/admin/users/new", methods=["GET", "POST"])
    @admin_required
    def admin_user_new():
        form_data = blank_user_form()

        if request.method == "POST":
            form_data = read_user_form(request.form)
            errors = validate_user_form(form_data, existing=None)

            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                user = User(
                    username=form_data["username"],
                    full_name=form_data["full_name"] or None,
                    email=form_data["email"] or None,
                    is_admin=form_data["is_admin"],
                    helpdesk_role=form_data["helpdesk_role"] or None,
                    is_active=True,
                    receives_notifications=form_data["receives_notifications"],
                    created_by=current_admin().username,
                )
                user.set_password(form_data["password"] or default_password(app))
                db.session.add(user)
                db.session.commit()
                flash(f"Account {user.username} created.", "success")
                return redirect(url_for("admin_user_edit", user_id=user.id))

        return render_template(
            "admin_user_form.html",
            form_data=form_data,
            user=None,
            helpdesk_roles=HELPDESK_ROLES,
            default_user_password=default_password(app),
        )

    @app.route("/admin/users/<int:user_id>", methods=["GET", "POST"])
    @admin_required
    def admin_user_edit(user_id: int):
        user = db.session.get(User, user_id)
        if user is None:
            flash("No such account.", "danger")
            return redirect(url_for("admin_users"))

        form_data = user_to_form(user)

        if request.method == "POST":
            form_data = read_user_form(request.form, username=user.username)
            errors = validate_user_form(form_data, existing=user)
            errors += rights_guardrails(form_data, user, current_admin())

            if errors:
                for error in errors:
                    flash(error, "danger")
            else:
                user.full_name = form_data["full_name"] or None
                user.email = form_data["email"] or None
                user.is_admin = form_data["is_admin"]
                user.helpdesk_role = form_data["helpdesk_role"] or None
                user.receives_notifications = form_data["receives_notifications"]
                db.session.commit()
                flash(f"Rights updated for {user.username}.", "success")
                return redirect(url_for("admin_user_edit", user_id=user.id))

        return render_template(
            "admin_user_form.html",
            form_data=form_data,
            user=user,
            helpdesk_roles=HELPDESK_ROLES,
            default_user_password=default_password(app),
        )

    @app.route("/admin/users/<int:user_id>/password", methods=["POST"])
    @admin_required
    def admin_user_password(user_id: int):
        user = db.session.get(User, user_id)
        if user is None:
            flash("No such account.", "danger")
            return redirect(url_for("admin_users"))

        password = request.form.get("password", "").strip() or default_password(app)
        if len(password) < 6:
            flash("A password must be at least 6 characters.", "danger")
        else:
            user.set_password(password)
            db.session.commit()
            flash(f"Password reset for {user.username}.", "success")

        return redirect(url_for("admin_user_edit", user_id=user.id))

    @app.route("/admin/users/<int:user_id>/status", methods=["POST"])
    @admin_required
    def admin_user_status(user_id: int):
        user = db.session.get(User, user_id)
        admin_user = current_admin()

        if user is None:
            flash("No such account.", "danger")
            return redirect(url_for("admin_users"))

        activate = request.form.get("activate") == "1"

        if not activate and user.id == admin_user.id:
            flash("You cannot deactivate your own account.", "danger")
        elif not activate and user.is_admin and last_active_admin(user):
            flash("This is the only active administrator; leave at least one.", "danger")
        else:
            user.is_active = activate
            db.session.commit()
            flash(
                f"{user.username} is now {'active' if activate else 'deactivated'}.",
                "success",
            )

        return redirect(url_for("admin_user_edit", user_id=user.id))

    @app.route("/admin/summary")
    @admin_required
    def admin_summary():
        """Small JSON view used by the console tiles."""
        return {
            "users": User.query.count(),
            "admins": User.query.filter_by(is_admin=True, is_active=True).count(),
            "helpdesk": User.query.filter(User.helpdesk_role.isnot(None)).count(),
            "reports": MaintenanceReport.query.count(),
        }


# --------------------------------------------------------------------------- #
# Form handling
# --------------------------------------------------------------------------- #

FORM_FIELDS = ("username", "full_name", "email", "helpdesk_role", "password")


def blank_user_form() -> dict:
    return {
        "username": "",
        "full_name": "",
        "email": "",
        "helpdesk_role": "",
        "password": "",
        "is_admin": False,
        "receives_notifications": True,
    }


def user_to_form(user: User) -> dict:
    return {
        "username": user.username,
        "full_name": user.full_name or "",
        "email": user.email or "",
        "helpdesk_role": user.helpdesk_role or "",
        "password": "",
        "is_admin": user.is_admin,
        "receives_notifications": user.receives_notifications,
    }


def read_user_form(submitted, username: str | None = None) -> dict:
    data = {field: submitted.get(field, "").strip() for field in FORM_FIELDS}
    if username is not None:
        # The username is the account's identity; editing rights never renames it.
        data["username"] = username
    data["is_admin"] = "is_admin" in submitted
    data["receives_notifications"] = "receives_notifications" in submitted
    return data


def validate_user_form(form_data: dict, existing: User | None) -> list[str]:
    errors = []

    username = form_data["username"]
    if not username:
        errors.append("Username is required.")
    elif existing is None and User.query.filter_by(username=username).first():
        errors.append("That username already exists.")

    email = form_data["email"]
    if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
        errors.append("Enter a valid email address, or leave it blank.")

    role = form_data["helpdesk_role"]
    if role and role not in HELPDESK_ROLES:
        errors.append("Choose a valid help desk role.")

    password = form_data["password"]
    if password and len(password) < 6:
        errors.append("A password must be at least 6 characters.")

    return errors


def rights_guardrails(form_data: dict, user: User, admin_user: User) -> list[str]:
    """Stop an administrator removing the rights that let anyone back in."""
    errors = []

    if user.is_admin and not form_data["is_admin"]:
        if user.id == admin_user.id:
            errors.append("You cannot remove your own administrator rights.")
        elif last_active_admin(user):
            errors.append("This is the only active administrator; leave at least one.")

    return errors


def last_active_admin(user: User) -> bool:
    others = User.query.filter(
        User.is_admin.is_(True), User.is_active.is_(True), User.id != user.id
    ).count()
    return others == 0


def default_password(app) -> str:
    return app.config["DEFAULT_USER_PASSWORD"]
