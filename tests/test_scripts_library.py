"""The Scripts page and the .ps1 / .cmd downloads it offers."""

import base64
import re

import pytest

from conftest import sign_in

from form_schema import field_names
from scripts_library import MAINTENANCE_SCRIPTS, cmd_file, find_script, powershell_file


@pytest.fixture(autouse=True)
def signed_in(client):
    """The portal is gated. These tests are about its pages, not its door."""
    sign_in(client, "icthelpdesk", "field.123")


def test_every_script_targets_a_real_form_field():
    names = field_names()
    for script in MAINTENANCE_SCRIPTS:
        assert script["field"] in names, script["key"]


def test_script_keys_are_unique():
    keys = [script["key"] for script in MAINTENANCE_SCRIPTS]
    assert len(keys) == len(set(keys))


def test_scripts_cover_the_new_report_detail_fields():
    fields = {script["field"] for script in MAINTENANCE_SCRIPTS}
    assert {"serial_no", "computer_name", "desktop_sno", "desktop_model"} <= fields


def test_powershell_self_elevates_and_reports():
    body = powershell_file(find_script("autoruns"))
    assert "-Verb RunAs" in body
    assert "Set-Clipboard" in body
    assert "Tee-Object" in body


def test_cmd_wrapper_elevates_and_carries_the_same_powershell():
    script = find_script("free-disk-space")
    wrapper = cmd_file(script)

    assert "Start-Process -FilePath '%~f0' -Verb RunAs" in wrapper
    payload = "".join(re.findall(r'>>"%B64%" echo (\S+)', wrapper))
    assert base64.b64decode(payload).decode("utf-8") == powershell_file(script)
    # Batch lines must stay well inside the command line length limit.
    assert max(len(line) for line in wrapper.splitlines()) < 250


def test_scripts_page_lists_every_script(client):
    response = client.get("/scripts")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    for script in MAINTENANCE_SCRIPTS:
        assert script["title"] in page
        assert f"/scripts/{script['key']}.ps1" in page
        assert f"/scripts/{script['key']}.cmd" in page


def test_downloads_are_served_as_attachments(client):
    for extension in ("ps1", "cmd"):
        response = client.get(f"/scripts/autoruns.{extension}")

        assert response.status_code == 200
        assert response.headers["Content-Disposition"] == (
            f'attachment; filename="autoruns.{extension}"'
        )


def test_unknown_script_or_extension_is_not_found(client):
    assert client.get("/scripts/does-not-exist.ps1").status_code == 404
    assert client.get("/scripts/autoruns.exe").status_code == 404


def test_maintenance_page_links_to_the_scripts(client):
    page = client.get("/maintenance").get_data(as_text=True)

    assert "/scripts" in page
    assert ">Scripts</a>" in page
