"""The organisation's ICT Computer Register.

The register is exported from the PBO Regulatory Authority assets workbook
(sheet "ICT Computer Register") into ``data/ict_computer_register.csv``. It is
loaded into ``computer_assets`` at seed time, and the maintenance form searches
it so an officer types a serial number once instead of typing the serial, the
model, and the officer's own name.
"""

import csv
from pathlib import Path

from sqlalchemy import or_

from models import ComputerAsset, db


REGISTER_CSV = Path(__file__).with_name("data") / "ict_computer_register.csv"

# An officer types the first few characters of a serial; below this a search
# would return most of the register, which is no help in a dropdown.
MIN_QUERY_LENGTH = 3
MAX_SUGGESTIONS = 12

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

    prefix_matches = (
        ComputerAsset.query.filter(
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
        ComputerAsset.query.filter(
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
