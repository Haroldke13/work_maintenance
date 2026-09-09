import base64
import math
import struct
import zlib
from datetime import date, time

from form_schema import SIGNATURE_DATA_URL_PREFIX


SIGNATURE_WIDTH, SIGNATURE_HEIGHT = 240, 80


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def sample_signature(seed: float) -> str:
    """A drawn-looking signature as the PNG data URL the pad would post.

    Seed data has to carry the same shape as a real signature so the seeded
    reports render — and can be edited — exactly like submitted ones. The PNG is
    written by hand (8-bit greyscale, one filter byte per row) to keep the seed
    free of an image dependency.
    """
    rows = [bytearray([255] * SIGNATURE_WIDTH) for _ in range(SIGNATURE_HEIGHT)]
    for x in range(8, SIGNATURE_WIDTH - 8):
        angle = (x / SIGNATURE_WIDTH) * math.tau * 2 + seed
        y = SIGNATURE_HEIGHT / 2 + math.sin(angle) * (SIGNATURE_HEIGHT / 4)
        for thickness in (-1, 0, 1):
            row = int(y) + thickness
            if 0 <= row < SIGNATURE_HEIGHT:
                rows[row][x] = 0

    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", SIGNATURE_WIDTH, SIGNATURE_HEIGHT, 8, 0, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw, 9))
        + _png_chunk(b"IEND", b"")
    )
    return SIGNATURE_DATA_URL_PREFIX + base64.b64encode(png).decode("ascii")


def initial_maintenance_reports() -> list[dict]:
    """Two example NGOB/ICT/104b reports used to prime an empty database."""
    first_report = {
        "serial_no": "NGOB/ICT/104b/0001",
        "computer_name": "NGOB-PC-001",
        "desktop_sno": "DSK-SN-0001",
        "desktop_model": "HP ProDesk 400 G7",
        "department": "ICT Department",
        "officer_name": "Sample Officer One",
        "report_time": time(9, 30),
        "report_date": date(2026, 9, 1),
        "peripherals_cleaned": True,
        "data_backup_schedule_status": "Weekly backup to the shared drive, last run 29 Aug 2026.",
        "windows_firewall_status": "Enabled on domain, private, and public profiles.",
        "allowed_firewall_exceptions": "File and Printer Sharing\nRemote Desktop\nCore Networking",
        "windows_update_status": "Up to date, last checked 1 Sep 2026.",
        "unneeded_running_services": "Fax\nWindows Media Player Network Sharing Service",
        "autoruns": "OneDrive\nMicrosoft Teams\nAntivirus tray agent",
        "unneeded_software": "Toolbar add-on\nTrial media player",
        "antivirus_auto_protect_status": "Active and scanning in real time.",
        "last_antivirus_update": date(2026, 8, 31),
        "windows_user_accounts": "Administrator\nngob.officer",
        "disk_defragmentation_done": True,
        "free_disk_space": "118 GB of 256 GB",
        "other_observations": "Cooling fan noisy under load; scheduled for follow-up.",
        "officer_sign_name": "Sample Officer One",
        "officer_signature": sample_signature(0.0),
        "officer_sign_date": date(2026, 9, 1),
        "ict_assigned_officer_name": "jonyango",
        "ict_assigned_officer_signature": sample_signature(0.7),
        "ict_assigned_officer_sign_date": date(2026, 9, 1),
        "ict_manager_name": "ICT Manager",
        "ict_manager_signature": sample_signature(1.4),
        "ict_manager_sign_date": date(2026, 9, 2),
    }

    second_report = {
        "serial_no": "NGOB/ICT/104b/0002",
        "computer_name": "NGOB-PC-002",
        "desktop_sno": "DSK-SN-0002",
        "desktop_model": "Dell OptiPlex 3080",
        "department": "Finance Office",
        "officer_name": "Sample Officer Two",
        "report_time": time(14, 15),
        "report_date": date(2026, 9, 1),
        "peripherals_cleaned": True,
        "data_backup_schedule_status": "Daily backup schedule pending re-configuration.",
        "windows_firewall_status": "Enabled, public profile blocking all inbound.",
        "allowed_firewall_exceptions": "Core Networking\nAccounting client",
        "windows_update_status": "Two optional updates pending a restart.",
        "unneeded_running_services": "Print Spooler (no printer attached)",
        "autoruns": "OneDrive\nAccounting client updater",
        "unneeded_software": "Trial PDF editor",
        "antivirus_auto_protect_status": "Active, definitions current.",
        "last_antivirus_update": date(2026, 9, 1),
        "windows_user_accounts": "Administrator\nfinance.officer\nfinance.temp",
        "disk_defragmentation_done": False,
        "free_disk_space": "64 GB of 500 GB",
        "other_observations": "Free disk space low; requested archive of old records.",
        "officer_sign_name": "Sample Officer Two",
        "officer_signature": sample_signature(2.1),
        "officer_sign_date": date(2026, 9, 1),
        "ict_assigned_officer_name": "jonyango",
        "ict_assigned_officer_signature": sample_signature(0.7),
        "ict_assigned_officer_sign_date": date(2026, 9, 1),
        "ict_manager_name": "ICT Manager",
        "ict_manager_signature": sample_signature(1.4),
        "ict_manager_sign_date": date(2026, 9, 2),
    }

    return [first_report, second_report]
