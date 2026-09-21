from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


__all__ = [
    "db",
    "HELPDESK_ROLES",
    "STAFF_ACTOR_ROLES",
    "User",
    "MaintenanceReport",
    "ComputerAsset",
]


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
    # Where the account came from, and whether its address has been proved.
    #
    # Only a self-registered account has to confirm: nobody vouched for the
    # address it typed in. An account staff created is vouched for by the
    # person who created it and handed the password over off-line, so it
    # signs in straight away. Defaulting to False keeps that true for every
    # account made in code — seeds, fixtures, the admin console.
    self_registered = db.Column(db.Boolean, nullable=False, default=False)
    email_confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
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

    def confirm_email(self) -> None:
        self.email_confirmed_at = datetime.now(timezone.utc)

    @property
    def awaiting_email_confirmation(self) -> bool:
        """Signed up for itself and has not yet clicked the emailed link."""
        return self.self_registered and self.email_confirmed_at is None

    @property
    def may_sign_in(self) -> bool:
        return self.is_active and not self.awaiting_email_confirmation

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
    desktop_sno = db.Column(db.String(50), nullable=True)
    desktop_model = db.Column(db.String(120), nullable=True)
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

    # Sign-off. The three signature columns hold a PNG data URL drawn on the
    # signature pad, so they are Text rather than a short String.
    officer_sign_name = db.Column(db.String(120), nullable=True)
    officer_signature = db.Column(db.Text, nullable=True)
    officer_sign_date = db.Column(db.Date, nullable=True)
    ict_assigned_officer_name = db.Column(db.String(120), nullable=True)
    ict_assigned_officer_signature = db.Column(db.Text, nullable=True)
    ict_assigned_officer_sign_date = db.Column(db.Date, nullable=True)
    ict_manager_name = db.Column(db.String(120), nullable=True)
    ict_manager_signature = db.Column(db.Text, nullable=True)
    ict_manager_sign_date = db.Column(db.Date, nullable=True)

    submitted_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    submitted_by_username = db.Column(db.String(80), nullable=True)

    # The register line this report was filed against. Null when the machine is
    # not on the register, so a report can still be filed for anything.
    asset_id = db.Column(
        db.Integer,
        db.ForeignKey("computer_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    asset = db.relationship("ComputerAsset", back_populates="reports")

    # Set when an ICT manager edits an already-submitted report.
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    updated_by_username = db.Column(db.String(80), nullable=True)

    def value_for(self, field_name: str):
        return getattr(self, field_name, None)

    @property
    def was_edited(self) -> bool:
        return self.updated_at is not None


class ComputerAsset(db.Model):
    """One line of the organisation's ICT Computer Register.

    The register is the authority on which officer holds which machine, so the
    maintenance form looks a serial number up here and fills in the officer and
    the model rather than asking them to be typed again.
    """

    __tablename__ = "computer_assets"

    id = db.Column(db.Integer, primary_key=True)

    # The first serial on the register line — the CPU's — is the one an officer
    # searches by. Serials repeat across a few lines, so this is not unique.
    serial_no = db.Column(db.String(120), nullable=True, index=True)
    # Every serial on the line (CPU, monitor, ...), so a monitor's serial finds
    # its machine too.
    all_serials = db.Column(db.Text, nullable=True)
    tag_numbers = db.Column(db.Text, nullable=True)

    asset_description = db.Column(db.String(200), nullable=True)
    make_model = db.Column(db.String(300), nullable=True)
    responsible_officer = db.Column(db.String(160), nullable=True, index=True)
    location = db.Column(db.String(120), nullable=True)
    condition = db.Column(db.String(60), nullable=True)
    notes = db.Column(db.String(200), nullable=True)

    reports = db.relationship(
        "MaintenanceReport", back_populates="asset", passive_deletes=True
    )

    @property
    def label(self) -> str:
        """How the register line reads on a report page."""
        parts = [self.serial_no, self.asset_description, self.make_model]
        return " · ".join(part for part in parts if part)

    def as_suggestion(self) -> dict:
        """The shape the form's serial-number dropdown consumes."""
        return {
            "id": self.id,
            "serial_no": self.serial_no or "",
            "make_model": self.make_model or "",
            "responsible_officer": self.responsible_officer or "",
            "asset_description": self.asset_description or "",
            "location": self.location or "",
            "tag_numbers": self.tag_numbers or "",
        }
