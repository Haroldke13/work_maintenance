#!/usr/bin/env python3
"""Copy Gmail SMTP settings from another env file without printing secrets."""

from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

COPIED_KEYS = ("MAIL_USERNAME", "MAIL_PASSWORD")
DEFAULTS = {
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": "587",
    "MAIL_USE_TLS": "true",
    "MAIL_SENDER_NAME": "PBORA",
    "NOTIFY_EMAILS": "jonyango@pbora.go.ke",
    "ADMIN_EMAIL": "jonyango@pbora.go.ke",
    "SUPPORT_EMAIL": "ictsupport@pbora.go.ke",
}


def read_env(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return lines, values


def update_env(target: Path, updates: dict[str, str]) -> None:
    lines, _ = read_env(target)
    remaining = dict(updates)
    output: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    if remaining:
        if output and output[-1]:
            output.append("")
        output.extend(f"{key}={value}" for key, value in remaining.items())
    mode = target.stat().st_mode & 0o777
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write("\n".join(output) + "\n")
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, target)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", default=Path(__file__).with_name(".env"), type=Path)
    args = parser.parse_args()
    _, source = read_env(args.source.resolve())
    _, target = read_env(args.target.resolve())
    missing = [key for key in COPIED_KEYS if not source.get(key)]
    if missing:
        raise SystemExit(f"Source is missing required Gmail settings: {', '.join(missing)}")
    updates = {key: source[key] for key in COPIED_KEYS}
    updates.update({key: target.get(key) or value for key, value in DEFAULTS.items()})
    # Notification delivery is intentionally restricted to this configured address.
    updates["NOTIFY_EMAILS"] = DEFAULTS["NOTIFY_EMAILS"]
    updates["MAIL_DEFAULT_SENDER"] = target.get("MAIL_DEFAULT_SENDER") or source["MAIL_USERNAME"]
    update_env(args.target.resolve(), updates)
    print(f"Configured Gmail SMTP in {args.target.resolve()} (secret values hidden).")


if __name__ == "__main__":
    main()
