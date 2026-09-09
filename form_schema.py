"""Field metadata for the Public Benefit Organizations Regulatory Authority Computer Maintenance Report.

The paper form is NGOB/ICT/104b. Every field name below matches a column on
``models.MaintenanceReport`` so the same metadata drives the form, the
validation, and the record tables.
"""

YES_NO_OPTIONS = [
    ("", "Not recorded"),
    ("Yes", "Yes"),
    ("No", "No"),
]

FIELD_SECTIONS = [
    {
        "title": "Report Details",
        "description": "Header of the NGOB/ICT/104b maintenance report.",
        "fields": [
            {
                "name": "serial_no",
                "label": "Chassis SNo (from BIOS)",
                "type": "text",
                "help": (
                    "Serial number reported by the BIOS. Type the first three "
                    "characters to search the ICT Computer Register."
                ),
            },
            {
                "name": "computer_name",
                "label": "Chassis Model (from BIOS)",
                "type": "text",
                "required": True,
                "help": "Make and model from the BIOS, e.g. HP ProBook G5.",
            },
            {
                "name": "desktop_sno",
                "label": "Desktop SNo (from the desktop)",
                "type": "text",
                "help": "Serial number printed on the desktop unit itself.",
            },
            {
                "name": "desktop_model",
                "label": "Desktop Model",
                "type": "text",
                "help": "Make and model of the desktop, e.g. HP ProDesk 400 G7.",
            },
            {"name": "department", "label": "Department", "type": "text", "required": True},
            {
                "name": "officer_name",
                "label": "Officer Owning Computer",
                "type": "text",
                "required": True,
            },
            {"name": "report_time", "label": "Time", "type": "time"},
            {"name": "report_date", "label": "Date", "type": "date", "required": True},
        ],
    },
    {
        "title": "Services",
        "description": "The fourteen maintenance checks carried out on the computer.",
        "fields": [
            {
                "name": "peripherals_cleaned",
                "label": "1. Computer and peripherals cleaned?",
                "type": "yesno",
            },
            {
                "name": "data_backup_schedule_status",
                "label": "2. Status of data backup schedule",
                "type": "text",
                "full_width": True,
            },
            {
                "name": "windows_firewall_status",
                "label": "3. Windows firewall status",
                "type": "text",
                "full_width": True,
            },
            {
                "name": "allowed_firewall_exceptions",
                "label": "4. Allowed firewall exceptions",
                "type": "textarea",
                "help": "One exception per line.",
            },
            {
                "name": "windows_update_status",
                "label": "5. Windows update status",
                "type": "text",
                "full_width": True,
            },
            {
                "name": "unneeded_running_services",
                "label": "6. Unneeded running system services",
                "type": "textarea",
                "help": "One service per line.",
            },
            {
                "name": "autoruns",
                "label": "7. List of autoruns",
                "type": "textarea",
                "help": "One autorun entry per line.",
            },
            {
                "name": "unneeded_software",
                "label": "8. Unneeded software installations",
                "type": "textarea",
                "help": "One program per line.",
            },
            {
                "name": "antivirus_auto_protect_status",
                "label": "9. Anti-virus auto-protect status",
                "type": "text",
                "full_width": True,
            },
            {
                "name": "last_antivirus_update",
                "label": "10. Date of the last anti-virus update",
                "type": "date",
            },
            {
                "name": "windows_user_accounts",
                "label": "11. Windows user accounts",
                "type": "textarea",
                "help": "One account per line.",
            },
            {
                "name": "disk_defragmentation_done",
                "label": "12. Disk defragmentation done?",
                "type": "yesno",
            },
            {"name": "free_disk_space", "label": "13. Free disk space", "type": "text"},
            {
                "name": "other_observations",
                "label": "14. Any other observation made on computer",
                "type": "textarea",
            },
        ],
    },
    {
        "title": "Sign-Off",
        "description": "Names, signatures, and dates recorded at the foot of the report.",
        "fields": [
            {"name": "officer_sign_name", "label": "Officer name", "type": "text"},
            {
                "name": "officer_signature",
                "label": "Officer sign",
                "type": "signature",
                "help": "Sign with a mouse, pen, or finger.",
            },
            {"name": "officer_sign_date", "label": "Officer date", "type": "date"},
            {
                "name": "ict_assigned_officer_name",
                "label": "ICT assigned officer name",
                "type": "text",
            },
            {
                "name": "ict_assigned_officer_signature",
                "label": "ICT assigned officer sign",
                "type": "signature",
                "help": "Sign with a mouse, pen, or finger.",
            },
            {
                "name": "ict_assigned_officer_sign_date",
                "label": "ICT assigned officer date",
                "type": "date",
            },
            {"name": "ict_manager_name", "label": "ICT manager name", "type": "text"},
            {
                "name": "ict_manager_signature",
                "label": "ICT manager sign",
                "type": "signature",
                "help": "Sign with a mouse, pen, or finger.",
            },
            {"name": "ict_manager_sign_date", "label": "ICT manager date", "type": "date"},
        ],
    },
]


def iter_fields():
    for section in FIELD_SECTIONS:
        for field in section["fields"]:
            yield field


def field_names() -> list[str]:
    return [field["name"] for field in iter_fields()]


def blank_form_data() -> dict:
    return {field["name"]: field.get("default", "") for field in iter_fields()}


SIGNATURE_DATA_URL_PREFIX = "data:image/png;base64,"

# A generous ceiling for a pad-sized PNG, so a pasted or crafted value cannot
# grow the row without bound.
SIGNATURE_MAX_LENGTH = 500_000


def is_signature_data_url(value) -> bool:
    """True for a value the signature pad produced (and a browser can render)."""
    return isinstance(value, str) and value.startswith(SIGNATURE_DATA_URL_PREFIX)


def field_label(field_name: str) -> str:
    for field in iter_fields():
        if field["name"] == field_name:
            return field["label"]
    return field_name.replace("_", " ").title()
