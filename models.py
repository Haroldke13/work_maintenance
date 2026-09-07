from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


__all__ = ["db", "HELPDESK_ROLES", "STAFF_ACTOR_ROLES", "User", "MaintenanceReport"]


# Help desk capability held by a user account. `None` means no help desk access.
HELPDESK_ROLES = {
    "intern": "ICT intern",
    "officer": "Help desk officer",
    "manager": "ICT manager",
}

# Roles that work tickets, as recorded against actions in the audit trail.
STAFF_ACTOR_ROLES = ("intern", "officer", "manager")


class User(db.Model):
    """One account for the whole system: maintenance admin and help desk alike."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(160), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)
    helpdesk_role = db.Column(db.String(20), nullable=True)  # officer | manager | None
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    # Account holders are on the notification list by default.
    receives_notifications = db.Column(db.Boolean, nullable=False, default=True)
    created_by = db.Column(db.String(80), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def display_name(self) -> str:
        return self.full_name or self.username

    @property
    def is_helpdesk_staff(self) -> bool:
        return self.helpdesk_role in HELPDESK_ROLES

    @property
    def is_manager(self) -> bool:
        """Managers — and the system admin — may close tickets."""
        return self.helpdesk_role == "manager" or self.is_admin

    @property
    def is_mail_recipient(self) -> bool:
        return bool(self.is_active and self.receives_notifications and self.email)

    @property
    def helpdesk_actor_role(self) -> str:
        """The role recorded against this user's help desk actions."""
        if self.is_manager:
            return "manager"
        return self.helpdesk_role or "officer"

    @property
    def helpdesk_role_label(self) -> str | None:
        return HELPDESK_ROLES.get(self.helpdesk_role)

    @property
    def role_label(self) -> str:
        if self.is_admin:
            return "Administrator"
        return HELPDESK_ROLES.get(self.helpdesk_role, "User")


class MaintenanceReport(db.Model):
    """One completed NGOB/ICT/104b Computer Maintenance Report."""

    __tablename__ = "maintenance_reports"

    id = db.Column(db.Integer, primary_key=True)

    # Report details
    serial_no = db.Column(db.String(50), nullable=True)
    computer_name = db.Column(db.String(120), nullable=False)
    department = db.Column(db.String(120), nullable=False)
    officer_name = db.Column(db.String(120), nullable=False)
    report_time = db.Column(db.Time, nullable=True)
    report_date = db.Column(db.Date, nullable=False, index=True)

    # Services 1-14
    peripherals_cleaned = db.Column(db.Boolean, nullable=True)
    data_backup_schedule_status = db.Column(db.Text, nullable=True)
    windows_firewall_status = db.Column(db.Text, nullable=True)
    allowed_firewall_exceptions = db.Column(db.Text, nullable=True)
    windows_update_status = db.Column(db.Text, nullable=True)
    unneeded_running_services = db.Column(db.Text, nullable=True)
    autoruns = db.Column(db.Text, nullable=True)
    unneeded_software = db.Column(db.Text, nullable=True)
    antivirus_auto_protect_status = db.Column(db.Text, nullable=True)
    last_antivirus_update = db.Column(db.Date, nullable=True)
    windows_user_accounts = db.Column(db.Text, nullable=True)
    disk_defragmentation_done = db.Column(db.Boolean, nullable=True)
    free_disk_space = db.Column(db.String(60), nullable=True)
    other_observations = db.Column(db.Text, nullable=True)

    # Sign-off
    officer_sign_name = db.Column(db.String(120), nullable=True)
    officer_signature = db.Column(db.String(120), nullable=True)
    officer_sign_date = db.Column(db.Date, nullable=True)
    ict_assigned_officer_name = db.Column(db.String(120), nullable=True)
    ict_assigned_officer_signature = db.Column(db.String(120), nullable=True)
    ict_assigned_officer_sign_date = db.Column(db.Date, nullable=True)
    ict_manager_name = db.Column(db.String(120), nullable=True)
    ict_manager_signature = db.Column(db.String(120), nullable=True)
    ict_manager_sign_date = db.Column(db.Date, nullable=True)

    submitted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    submitted_by_username = db.Column(db.String(80), nullable=True)

    def value_for(self, field_name: str):
        return getattr(self, field_name, None)
