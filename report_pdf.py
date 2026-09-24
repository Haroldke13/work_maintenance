"""Dependency-free PDF extracts for computer maintenance reports."""

from __future__ import annotations

import re
import textwrap

from form_schema import FIELD_SECTIONS, is_signature_data_url


def _render(value) -> str:
    if is_signature_data_url(value):
        return "(signed)"
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    if value in (None, ""):
        return "-"
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d %H:%M" if hasattr(value, "hour") else "%Y-%m-%d")
    return str(value)


def _report_lines(report) -> list[str]:
    lines = [
        "PBORA COMPUTER MAINTENANCE REPORT (NGOB/ICT/104b)",
        f"Report #{report.id}",
        "",
    ]
    for section in FIELD_SECTIONS:
        lines.extend((section["title"].upper(), "-" * len(section["title"])))
        for field in section["fields"]:
            value = _render(report.value_for(field["name"]))
            logical_lines = value.splitlines() or [value]
            first = f"{field['label']}: {logical_lines[0]}"
            lines.extend(textwrap.wrap(first, width=92, break_long_words=False) or [""])
            for continuation in logical_lines[1:]:
                lines.extend(
                    textwrap.wrap(f"    {continuation}", width=92, break_long_words=False)
                    or ["    "]
                )
        lines.append("")
    lines.append(f"Submitted: {_render(report.submitted_at)} UTC")
    if report.submitted_by_username:
        lines.append(f"Submitted by: {report.submitted_by_username}")
    return lines


def _pdf_string(value: str) -> bytes:
    encoded = value.encode("cp1252", errors="replace")
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def maintenance_report_pdf(report) -> bytes:
    """Return a small, valid, paginated PDF containing every report field."""
    lines = _report_lines(report)
    page_lines = [lines[index : index + 54] for index in range(0, len(lines), 54)] or [[]]
    objects: list[bytes] = [b"", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    page_ids: list[int] = []
    for page in page_lines:
        page_id = len(objects) + 1
        content_id = page_id + 1
        page_ids.append(page_id)
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        commands = [b"BT", b"/F1 9 Tf", b"48 750 Td", b"12 TL"]
        for line in page:
            commands.extend((b"(" + _pdf_string(line) + b") Tj", b"T*"))
        commands.append(b"ET")
        stream = b"\n".join(commands)
        objects.append(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id, payload in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(payload)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(output)


def maintenance_report_pdf_filename(report) -> str:
    identity = report.serial_no or report.computer_name or f"report-{report.id}"
    safe_identity = re.sub(r"[^A-Za-z0-9._-]+", "-", str(identity)).strip("-.")
    return f"maintenance-report-{report.id}-{safe_identity or 'computer'}.pdf"
