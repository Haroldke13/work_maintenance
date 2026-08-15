from functools import wraps

from flask import Flask, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_migrate import Migrate

from config import Config
from form_schema import FIELD_SECTIONS, blank_form_data, iter_fields
from models import CleanupRecord, User, db
from seed_data import initial_cleanup_records


migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)

    register_template_filters(app)
    register_routes(app)
    register_commands(app)
    return app


def register_template_filters(app: Flask) -> None:
    @app.template_filter("display_value")
    def display_value(value):
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        if value in (None, ""):
            return "—"
        return value


def register_commands(app: Flask) -> None:
    @app.cli.command("init-db")
    def init_db_command():
        initialize_database(app)
        print("Database tables and seed data are ready.")

    @app.cli.command("seed-data")
    def seed_data_command():
        seed_database(app)
        print("Seed data is ready.")


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        return redirect(url_for("cleanup_form"))

    @app.route("/cleanup", methods=["GET", "POST"])
    def cleanup_form():
        if request.method == "POST":
            form_data = collect_form_data(request.form)
            errors = validate_required_fields(form_data)
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template(
                    "cleanup.html",
                    field_sections=FIELD_SECTIONS,
                    form_data=form_data,
                )

            record = CleanupRecord(form_data=form_data)
            db.session.add(record)
            db.session.commit()
            flash("Cleanup practical record saved.", "success")
            return redirect(url_for("table", record_id=record.id))

        return render_template(
            "cleanup.html",
            field_sections=FIELD_SECTIONS,
            form_data=blank_form_data(),
        )

    @app.route("/table/<int:record_id>")
    def table(record_id: int):
        record = db.session.get(CleanupRecord, record_id)
        if record is None:
            abort(404)
        return render_template(
            "table.html",
            field_sections=FIELD_SECTIONS,
            record=record,
        )

    @app.route("/admin", methods=["GET", "POST"])
    def admin():
        admin_user = current_admin()

        if request.method == "POST":
            action = request.form.get("action")
            if action == "login":
                username = request.form.get("username", "").strip()
                password = request.form.get("password", "")
                user = User.query.filter_by(username=username).first()
                if user and user.is_admin and user.check_password(password):
                    session["admin_user_id"] = user.id
                    flash("Admin login successful.", "success")
                    return redirect(url_for("admin"))
                flash("Invalid admin username or password.", "danger")

            elif action == "create_user":
                if admin_user is None:
                    flash("Admin login required before creating users.", "warning")
                    return redirect(url_for("admin"))

                username = request.form.get("username", "").strip()
                if not username:
                    flash("Username is required.", "danger")
                elif User.query.filter_by(username=username).first():
                    flash("That username already exists.", "danger")
                else:
                    user = User(username=username, is_admin=False, created_by=admin_user.username)
                    user.set_password(current_default_user_password())
                    db.session.add(user)
                    db.session.commit()
                    flash(f"User {username} created with the default password.", "success")
                return redirect(url_for("admin"))

        return render_template(
            "admin.html",
            admin_user=admin_user,
            users=User.query.order_by(User.created_at.desc()).all() if admin_user else [],
            default_user_password=current_default_user_password(),
            records_count=CleanupRecord.query.count() if admin_user else 0,
        )

    @app.route("/admin/logout", methods=["POST"])
    def admin_logout():
        session.pop("admin_user_id", None)
        flash("Logged out.", "info")
        return redirect(url_for("admin"))

    @app.route("/admin/records")
    @admin_required
    def all_records():
        records = CleanupRecord.query.order_by(CleanupRecord.id.asc()).all()
        return render_template(
            "all records.html",
            field_sections=FIELD_SECTIONS,
            records=records,
        )


def collect_form_data(submitted_form) -> dict:
    data = {}
    for field in iter_fields():
        field_name = field["name"]
        if field["type"] == "checkbox":
            data[field_name] = field_name in submitted_form
        else:
            data[field_name] = submitted_form.get(field_name, "").strip()
    return data


def validate_required_fields(form_data: dict) -> list[str]:
    errors = []
    for field in iter_fields():
        if field.get("required") and not str(form_data.get(field["name"], "")).strip():
            errors.append(f"{field['label']} is required.")
    return errors


def current_admin():
    admin_user_id = session.get("admin_user_id")
    if not admin_user_id:
        return None

    user = db.session.get(User, admin_user_id)
    if user and user.is_admin:
        return user
    session.pop("admin_user_id", None)
    return None


def admin_required(route_handler):
    @wraps(route_handler)
    def wrapped_route(*args, **kwargs):
        if current_admin() is None:
            flash("Admin login required.", "warning")
            return redirect(url_for("admin"))
        return route_handler(*args, **kwargs)

    return wrapped_route


def current_default_user_password() -> str:
    return current_app.config["DEFAULT_USER_PASSWORD"]


def initialize_database(app: Flask) -> None:
    with app.app_context():
        db.create_all()
    seed_database(app)


def seed_database(app: Flask) -> None:
    with app.app_context():
        seed_admin_user(app)
        seed_cleanup_records()
        db.session.commit()


def seed_admin_user(app: Flask) -> None:
    admin_username = app.config["ADMIN_USERNAME"]
    admin_password = app.config["ADMIN_PASSWORD"]
    admin_user = User.query.filter_by(username=admin_username).first()

    if admin_user is None:
        admin_user = User(username=admin_username, is_admin=True)
        admin_user.set_password(admin_password)
        db.session.add(admin_user)
        return

    admin_user.is_admin = True
    if not admin_user.check_password(admin_password):
        admin_user.set_password(admin_password)


def seed_cleanup_records() -> None:
    if CleanupRecord.query.count() > 0:
        return

    for record_data in initial_cleanup_records():
        db.session.add(CleanupRecord(form_data=record_data, submitted_by_username="seed"))


app = create_app()
