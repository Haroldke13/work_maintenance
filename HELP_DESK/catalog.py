"""Common office PC and laptop problems, plus the self-help steps shown to reporters.

Each category carries a default priority so a reporter never has to judge urgency,
and a short knowledge-base snippet so obvious problems can be fixed without a ticket.
"""

OTHER_KEY = "other"

PRIORITIES = {
    "urgent": {"label": "Urgent", "sla_hours": 2, "badge": "danger", "rank": 0},
    "high": {"label": "High", "sla_hours": 4, "badge": "warning", "rank": 1},
    "normal": {"label": "Normal", "sla_hours": 8, "badge": "primary", "rank": 2},
    "low": {"label": "Low", "sla_hours": 24, "badge": "secondary", "rank": 3},
}

STATUSES = {
    "open": {"label": "Open", "badge": "danger"},
    "in_progress": {"label": "In Progress", "badge": "warning"},
    "resolved": {"label": "Resolved", "badge": "success"},
    "closed": {"label": "Closed", "badge": "secondary"},
}

OPEN_STATUSES = ("open", "in_progress")

PROBLEM_CATEGORIES = [
    {
        "key": "pc_wont_start",
        "label": "Computer will not power on or boot",
        "priority": "urgent",
        "self_help": [
            "Check the power cable at both the wall socket and the computer.",
            "Hold the power button for 10 seconds, release, then press it once.",
            "For a laptop, remove the charger, hold power for 15 seconds, reconnect and retry.",
        ],
    },
    {
        "key": "slow_performance",
        "label": "Computer running slowly or freezing",
        "priority": "normal",
        "self_help": [
            "Restart the computer — most slowness clears after a restart.",
            "Close browser tabs and applications you are not using.",
            "Check free disk space; below 10% free will slow Windows down badly.",
        ],
    },
    {
        "key": "blue_screen",
        "label": "Blue screen, crashes or random restarts",
        "priority": "high",
        "self_help": [
            "Write down the stop code shown on the blue screen — it speeds up diagnosis.",
            "Note what you were doing when it crashed and whether it repeats.",
        ],
    },
    {
        "key": "no_internet",
        "label": "No internet or network connection",
        "priority": "high",
        "self_help": [
            "Check whether colleagues nearby are also offline — that points to the network, not your PC.",
            "Unplug the network cable, wait 10 seconds and plug it back in.",
            "For Wi-Fi, toggle Wi-Fi off and on, then reconnect to the office network.",
        ],
    },
    {
        "key": "printer",
        "label": "Printer or scanner not working",
        "priority": "normal",
        "self_help": [
            "Confirm the printer is powered on and has paper and toner.",
            "Check you selected the correct printer in the print dialog.",
            "Clear stuck jobs: right-click the printer, open the queue and cancel all documents.",
        ],
    },
    {
        "key": "email",
        "label": "Email not sending or receiving",
        "priority": "high",
        "self_help": [
            "Check the Outbox for a message that is stuck and delete it.",
            "Confirm you are online and can browse the internet.",
        ],
    },
    {
        "key": "password_account",
        "label": "Password reset or account locked out",
        "priority": "high",
        "self_help": [
            "Check Caps Lock and that you are typing the current password.",
            "An account usually unlocks itself after 30 minutes.",
        ],
    },
    {
        "key": "software_install",
        "label": "Software installation or licence request",
        "priority": "low",
        "self_help": [
            "State the exact software name and version, and why it is needed for your work.",
            "Licensed software needs approval from your head of department.",
        ],
    },
    {
        "key": "software_error",
        "label": "Application error or will not open",
        "priority": "normal",
        "self_help": [
            "Note the exact error message wording — a screenshot is ideal.",
            "Close the application completely and reopen it once.",
        ],
    },
    {
        "key": "peripheral",
        "label": "Keyboard, mouse, monitor or docking station fault",
        "priority": "normal",
        "self_help": [
            "Unplug the device and plug it into a different USB port.",
            "For a wireless device, replace the batteries.",
            "Check the monitor cable is firmly seated at both ends.",
        ],
    },
    {
        "key": "battery_power",
        "label": "Laptop battery not charging or adapter fault",
        "priority": "high",
        "self_help": [
            "Try a different power socket and confirm the charger light comes on.",
            "Check the charger cable for damage or a loose connector.",
        ],
    },
    {
        "key": "audio_video",
        "label": "No sound, microphone or camera not working",
        "priority": "high",
        "self_help": [
            "Check the volume is not muted and the correct output device is selected.",
            "In meeting software, open settings and pick the right microphone and camera.",
            "Close other applications that may be holding the camera.",
        ],
    },
    {
        "key": "storage_full",
        "label": "Disk full or out of storage",
        "priority": "normal",
        "self_help": [
            "Empty the Recycle Bin and clear the Downloads folder.",
            "Move completed work to the shared drive instead of the desktop.",
        ],
    },
    {
        "key": "file_recovery",
        "label": "Lost or deleted files, data recovery",
        "priority": "urgent",
        "self_help": [
            "Stop saving anything to the affected drive — it lowers the chance of recovery.",
            "Check the Recycle Bin and the file history of the shared folder first.",
        ],
    },
    {
        "key": "virus_malware",
        "label": "Virus, malware or suspicious pop-ups",
        "priority": "urgent",
        "self_help": [
            "Disconnect the network cable or Wi-Fi immediately to stop it spreading.",
            "Do not enter passwords or card details into any pop-up.",
            "Leave the computer on so ICT can inspect it.",
        ],
    },
    {
        "key": "phishing",
        "label": "Suspicious email or suspected phishing",
        "priority": "urgent",
        "self_help": [
            "Do not click links or open attachments in the message.",
            "Do not forward it to colleagues — report it here instead.",
        ],
    },
    {
        "key": "vpn_remote",
        "label": "VPN or remote access problem",
        "priority": "high",
        "self_help": [
            "Confirm your home internet works by opening any website.",
            "Disconnect and reconnect the VPN client once.",
        ],
    },
    {
        "key": "shared_drive",
        "label": "Shared folder or network drive not accessible",
        "priority": "high",
        "self_help": [
            "Note the exact folder path you are trying to open.",
            "Confirm whether the drive worked yesterday and what changed.",
        ],
    },
    {
        "key": "overheating",
        "label": "Laptop overheating or loud fan",
        "priority": "normal",
        "self_help": [
            "Use the laptop on a hard surface, not on a cloth or your lap.",
            "Check the vents are not blocked by dust or paper.",
        ],
    },
    {
        "key": "screen_display",
        "label": "Screen flickering, cracked or no display",
        "priority": "high",
        "self_help": [
            "Try a different cable or a different monitor if one is available.",
            "Press the Windows key + P and confirm the display mode.",
        ],
    },
    {
        "key": "backup",
        "label": "Backup failure or backup not running",
        "priority": "high",
        "self_help": [
            "Note when the last successful backup ran.",
            "Confirm the backup destination drive is connected.",
        ],
    },
    {
        "key": OTHER_KEY,
        "label": "Other (describe the problem below)",
        "priority": "normal",
        "self_help": [
            "Describe what happens, when it started, and any error message shown.",
        ],
    },
]

CATEGORIES_BY_KEY = {category["key"]: category for category in PROBLEM_CATEGORIES}


def category_choices() -> list[tuple[str, str]]:
    return [(category["key"], category["label"]) for category in PROBLEM_CATEGORIES]


def is_valid_category(key: str) -> bool:
    return key in CATEGORIES_BY_KEY


def default_priority(key: str) -> str:
    return CATEGORIES_BY_KEY.get(key, {}).get("priority", "normal")


def sla_hours(priority: str) -> int:
    return PRIORITIES.get(priority, PRIORITIES["normal"])["sla_hours"]


def category_label(key: str, other_category: str | None = None) -> str:
    if key == OTHER_KEY and other_category:
        return other_category
    return CATEGORIES_BY_KEY.get(key, {}).get("label", key)


def self_help_steps(key: str) -> list[str]:
    return CATEGORIES_BY_KEY.get(key, {}).get("self_help", [])
