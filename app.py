import os
from datetime import date, datetime, time

from flask import (
    Flask,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from admin_users import register_admin_user_routes
from auth import (
    admin_required,
    current_admin,
    current_user,
    landing_page_for,
    login_user,
    logout_user,
)
from config import Config
from extensions import db, migrate, socketio
from form_schema import FIELD_SECTIONS, blank_form_data, iter_fields
from HELP_DESK import register_helpdesk, seed_helpdesk
from models import HELPDESK_ROLES, MaintenanceReport, User
from notifications import email_maintenance_report
from scripts_library import cmd_file, find_script, powershell_file, script_groups
from seed_data import initial_maintenance_reports


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    socketio.init_app(app)

    register_template_filters(app)
    register_routes(app)
    register_commands(app)
    register_helpdesk(app)
    register_admin_user_routes(app)
    return app


def register_template_filters(app: Flask) -> None:
    @app.context_processor
    def inject_complaint_counts():
        """Powers the navbar Complaints button and its badge on every page."""
        user = current_user()
        if user is None:
            return {"current_user": None, "complaints_total": 0, "complaints_open": 0}

        from HELP_DESK import catalog as helpdesk_catalog
        from HELP_DESK.models import Ticket

        try:
            total = Ticket.query.count()
            open_count = Ticket.query.filter(
                Ticket.status.in_(helpdesk_catalog.OPEN_STATUSES)
            ).count()
        except Exception:
            total = open_count = 0

        return {"current_user": user, "complaints_total": total, "complaints_open": open_count}

    @app.template_filter("display_value")
    def display_value(value):
        if value is True:
            return "Yes"
        if value is False:
            return "No"
        if value in (None, ""):
            return "—"
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        if isinstance(value, date):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, time):
            return value.strftime("%H:%M")
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
        return redirect(url_for("maintenance_form"))

    @app.route("/maintenance", methods=["GET", "POST"])
    def maintenance_form():
        if request.method == "POST":
            form_data = collect_form_data(request.form)
            errors = validate_form_data(form_data)
            if errors:
                for error in errors:
                    flash(error, "danger")
                return render_template(
                    "maintenance.html",
                    field_sections=FIELD_SECTIONS,
                    form_data=form_data,
                )

            report = MaintenanceReport(**coerce_form_data(form_data))
            db.session.add(report)
            db.session.commit()
            email_maintenance_report(report)
            flash("Computer maintenance report saved.", "success")
            return redirect(url_for("table", report_id=report.id))

        return render_template(
            "maintenance.html",
            field_sections=FIELD_SECTIONS,
            form_data=blank_form_data(),
        )

    @app.route("/scripts")
    def scripts():
        """Collector scripts an officer runs before filling in the report."""
        return render_template("scripts.html", script_groups=script_groups())

    @app.route("/scripts/<key>.<ext>")
    def script_download(key: str, ext: str):
        """Serve one script as a .ps1 or its self-elevating .cmd wrapper."""
        script = find_script(key)
        if script is None or ext not in ("ps1", "cmd"):
            abort(404)

        body = powershell_file(script) if ext == "ps1" else cmd_file(script)
        return Response(
            body,
            mimetype="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{key}.{ext}"'},
        )

    @app.route("/table/<int:report_id>")
    def table(report_id: int):
        report = db.session.get(MaintenanceReport, report_id)
        if report is None:
            abort(404)
        return render_template(
            "table.html",
            field_sections=FIELD_SECTIONS,
            report=report,
        )

    @app.route("/login", methods=["GET", "POST"])
    def login():
        """One sign-in for the maintenance admin area and the ICT help desk."""
        next_url = request.values.get("next") or ""

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username, is_active=True).first()

            if user and user.check_password(password):
                login_user(user)
                flash(f"Signed in as {user.display_name}.", "success")
                return redirect(next_url or landing_page_for(user))
            flash("Invalid username or password.", "danger")

        return render_template("login.html", next_url=next_url, user=current_user())

    @app.route("/logout", methods=["POST"])
    def logout():
        logout_user()
        flash("Signed out.", "info")
        return redirect(url_for("login"))

    @app.route("/admin")
    @admin_required
    def admin():
        return render_template(
            "admin.html",
            admin_user=current_admin(),
            users=User.query.order_by(User.created_at.desc()).limit(8).all(),
            user_count=User.query.count(),
            admin_count=User.query.filter_by(is_admin=True, is_active=True).count(),
            helpdesk_count=User.query.filter(User.helpdesk_role.isnot(None)).count(),
            default_user_password=current_default_user_password(),
            reports_count=MaintenanceReport.query.count(),
        )

    @app.route("/admin/records")
    @admin_required
    def all_records():
        reports = MaintenanceReport.query.order_by(MaintenanceReport.id.asc()).all()
        return render_template(
            "all records.html",
            field_sections=FIELD_SECTIONS,
            reports=reports,
        )


def collect_form_data(submitted_form) -> dict:
    """Read the posted form into raw strings so an invalid post can be re-rendered."""
    return {
        field["name"]: submitted_form.get(field["name"], "").strip() for field in iter_fields()
    }


def validate_form_data(form_data: dict) -> list[str]:
    errors = []
    for field in iter_fields():
        value = form_data.get(field["name"], "")

        if field.get("required") and not value:
            errors.append(f"{field['label']} is required.")
            continue
        if not value:
            continue

        if field["type"] == "date" and parse_date(value) is None:
            errors.append(f"{field['label']} must be a valid date (YYYY-MM-DD).")
        elif field["type"] == "time" and parse_time(value) is None:
            errors.append(f"{field['label']} must be a valid time (HH:MM).")
        elif field["type"] == "yesno" and value not in ("Yes", "No"):
            errors.append(f"{field['label']} must be Yes or No.")
    return errors


def coerce_form_data(form_data: dict) -> dict:
    """Turn validated form strings into the Python values the columns expect."""
    coerced = {}
    for field in iter_fields():
        value = form_data.get(field["name"], "")
        field_type = field["type"]

        if field_type == "yesno":
            coerced[field["name"]] = {"Yes": True, "No": False}.get(value)
        elif field_type == "date":
            coerced[field["name"]] = parse_date(value)
        elif field_type == "time":
            coerced[field["name"]] = parse_time(value)
        else:
            coerced[field["name"]] = value or None
    return coerced


def parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_time(value: str):
    for time_format in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, time_format).time()
        except ValueError:
            continue
    return None


def current_default_user_password() -> str:
    return current_app.config["DEFAULT_USER_PASSWORD"]


def initialize_database(app: Flask) -> None:
    with app.app_context():
        db.create_all()
    seed_database(app)


def seed_database(app: Flask) -> None:
    with app.app_context():
        seed_accounts(app)
        seed_maintenance_reports()
        db.session.commit()
        seed_helpdesk(app)


def _support_email(app: Flask) -> str | None:
    """The shared ICT address: the notify list minus the administrator's own."""
    admin_email = app.config.get("ADMIN_EMAIL")
    others = [a for a in app.config.get("NOTIFY_EMAILS", []) if a != admin_email]
    return others[0] if others else admin_email


def seed_accounts(app: Flask) -> None:
    """One account table for the admin area and the help desk alike."""
    accounts = [
        {
            "username": app.config["ADMIN_USERNAME"],
            "password": app.config["ADMIN_PASSWORD"],
            "full_name": "ICT Administrator",
            "email": app.config["ADMIN_EMAIL"],
            "is_admin": True,
            "helpdesk_role": "manager",
        },
        {
            "username": app.config["HELPDESK_MANAGER_USERNAME"],
            "password": app.config["HELPDESK_MANAGER_PASSWORD"],
            "full_name": "ICT Manager",
            "email": _support_email(app),
            "is_admin": False,
            "helpdesk_role": "manager",
        },
        {
            "username": app.config["HELPDESK_OFFICER_USERNAME"],
            "password": app.config["HELPDESK_OFFICER_PASSWORD"],
            "full_name": "ICT Help Desk Officer",
            "email": _support_email(app),
            "is_admin": False,
            "helpdesk_role": "officer",
        },
    ]

    for account in accounts:
        user = User.query.filter_by(username=account["username"]).first()

        if user is None:
            user = User(
                username=account["username"],
                full_name=account["full_name"],
                email=account["email"],
                is_admin=account["is_admin"],
                helpdesk_role=account["helpdesk_role"],
            )
            user.set_password(account["password"])
            db.session.add(user)
            continue

        user.full_name = user.full_name or account["full_name"]
        user.email = user.email or account["email"]
        user.is_admin = account["is_admin"] or user.is_admin
        user.helpdesk_role = account["helpdesk_role"]
        user.is_active = True
        if not user.check_password(account["password"]):
            user.set_password(account["password"])


def seed_maintenance_reports() -> None:
    if MaintenanceReport.query.count() > 0:
        return

    for report_data in initial_maintenance_reports():
        db.session.add(MaintenanceReport(submitted_by_username="seed", **report_data))


app = create_app()


if __name__ == "__main__":
    # socketio.run keeps WebSocket support that a plain `flask run` would drop.
    socketio.run(
        app,
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "5000")),
        debug=True,
        allow_unsafe_werkzeug=True,
    )
