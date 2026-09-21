"""The organisation's ICT Computer Register.

The register is exported from the PBO Regulatory Authority assets workbook
(sheet "ICT Computer Register") into ``data/ict_computer_register.csv``. It is
loaded into ``computer_assets`` at seed time, and the maintenance form searches
it so an officer types a serial number once instead of typing the serial, the
model, and the officer's own name.
"""

import csv
from pathlib import Path

from sqlalchemy import case, or_

from models import ComputerAsset, db


REGISTER_CSV = Path(__file__).with_name("data") / "ict_computer_register.csv"

# An officer types the first few characters of a serial; below this a search
# would return most of the register, which is no help in a dropdown.
MIN_QUERY_LENGTH = 3
MAX_SUGGESTIONS = 12

# The asset descriptions that are a computer somebody can file a Computer
# Maintenance Report (NGOB/ICT/104b) against.
#
# The register covers all of ICT's assets, so most of its lines are not
# machines at all: telephone heads, printers, switches, a shredder, an air
# conditioner. Only these two descriptions are, and the workbook writes each
# as a multi-line cell — "CPU / Monitor / Keyboard" is one desktop set listed
# by its parts, not three assets. Matched lowercased and trimmed, so a stray
# space or a change of case in a future export still lands.
COMPUTER_DESCRIPTIONS = frozenset(
    {
        "cpu / monitor / keyboard",
        "laptop computer",
    }
)


def is_computer(asset_description: str) -> bool:
    return (asset_description or "").strip().lower() in COMPUTER_DESCRIPTIONS


# The branch a machine sits at, from the register's "Current Location" column.
# Head office leads the page; every other branch follows in alphabetical order.
HEADQUARTERS = "Nairobi"
NO_BRANCH = "No branch recorded"

# The workbook spells two branches more than one way. Left alone they would
# open as two accordions for one office, so they are folded together here.
BRANCH_ALIASES = {"garisa": "Garissa"}


def branch_of(location: str) -> str:
    """The branch name to group a register line under.

    Title-cased, so "NAKURU" and "Nakuru" are one branch rather than two.
    """
    name = (location or "").strip()
    if not name:
        return NO_BRANCH
    return BRANCH_ALIASES.get(name.lower(), name.title())


def _branch_order(name: str) -> tuple:
    if name == HEADQUARTERS:
        return (0, "")
    if name == NO_BRANCH:
        return (2, "")
    return (1, name)


def computers_by_branch() -> list[tuple[str, list[ComputerAsset]]]:
    """Every computer on the register, grouped by branch, Nairobi first.

    Within a branch the order is the one the page has always used: machines an
    officer can act on lead, and the register's unassigned lines follow.
    """
    unassigned = case(
        (
            or_(
                ComputerAsset.responsible_officer.is_(None),
                ComputerAsset.responsible_officer == "",
            ),
            1,
        ),
        else_=0,
    )
    assets = (
        only_computers(ComputerAsset.query)
        .order_by(unassigned, ComputerAsset.responsible_officer, ComputerAsset.serial_no)
        .all()
    )

    branches: dict[str, list[ComputerAsset]] = {}
    for asset in assets:
        branches.setdefault(branch_of(asset.location), []).append(asset)

    return [(name, branches[name]) for name in sorted(branches, key=_branch_order)]


def only_computers(query):
    """Narrow a ComputerAsset query to the lines that are a computer."""
    return query.filter(
        db.func.lower(db.func.trim(ComputerAsset.asset_description)).in_(
            COMPUTER_DESCRIPTIONS
        )
    )

FIELDS = (
    "serial_no",
    "all_serials",
    "tag_numbers",
    "asset_description",
    "make_model",
    "responsible_officer",
    "location",
    "condition",
    "notes",
)


def read_register(path: Path = REGISTER_CSV) -> list[dict]:
    """Every register line as a dict, straight from the CSV export."""
    if not path.exists():
        return []

    with path.open(newline="", encoding="utf-8") as handle:
        return [
            {field: (row.get(field) or "").strip() for field in FIELDS}
            for row in csv.DictReader(handle)
        ]


def seed_computer_assets() -> int:
    """Load the register once. Returns the number of assets in the table."""
    if ComputerAsset.query.count() > 0:
        return ComputerAsset.query.count()

    entries = read_register()
    for entry in entries:
        db.session.add(ComputerAsset(**entry))
    return len(entries)


def search_assets(query: str, limit: int = MAX_SUGGESTIONS) -> list[ComputerAsset]:
    """Register lines matching a partial serial number, tag, or officer name.

    Serial numbers that *start* with what was typed come first — that is what an
    officer reading a sticker is doing — then anything else that contains it.
    """
    query = (query or "").strip()
    if len(query) < MIN_QUERY_LENGTH:
        return []

    starts_with = f"{query}%"
    contains = f"%{query}%"

    # Same sieve as the register page: this dropdown prefills a Computer
    # Maintenance Report, and a telephone's serial has no such report to fill.
    prefix_matches = (
        only_computers(ComputerAsset.query).filter(
            or_(
                ComputerAsset.serial_no.ilike(starts_with),
                ComputerAsset.all_serials.ilike(starts_with),
                ComputerAsset.tag_numbers.ilike(starts_with),
            )
        )
        .order_by(ComputerAsset.serial_no)
        .limit(limit)
        .all()
    )

    results = list(prefix_matches)
    if len(results) >= limit:
        return results

    seen = {asset.id for asset in results}
    other_matches = (
        only_computers(ComputerAsset.query).filter(
            or_(
                ComputerAsset.serial_no.ilike(contains),
                ComputerAsset.all_serials.ilike(contains),
                ComputerAsset.tag_numbers.ilike(contains),
                ComputerAsset.responsible_officer.ilike(contains),
            )
        )
        .order_by(ComputerAsset.serial_no)
        .limit(limit * 2)
        .all()
    )

    for asset in other_matches:
        if asset.id not in seen:
            results.append(asset)
            if len(results) >= limit:
                break
    return results
