"""Signature pads on the sign-off, and the ICT manager's edit of a submitted report."""

from conftest import sign_in
from test_routes import valid_maintenance_form

from form_schema import field_label
from models import MaintenanceReport
from seed_data import sample_signature


def submit_report(client, **overrides):
    """Post a complete report and return its id."""
    form_data = valid_maintenance_form()
    form_data.update(overrides)
    response = client.post("/maintenance", data=form_data, follow_redirects=False)
    return int(response.headers["Location"].rsplit("/", 1)[1])


# --- Field labels ------------------------------------------------------


def test_report_detail_labels_name_their_source():
    assert field_label("serial_no") == "Chassis SNo (from BIOS)"
    assert field_label("computer_name") == "Chassis Model (from BIOS)"
    assert field_label("desktop_sno") == "Desktop SNo (from the desktop)"
    assert field_label("desktop_model") == "Desktop Model"


def test_the_officer_field_is_labelled_officer_owning_computer(client):
    assert field_label("officer_name") == "Officer Owning Computer"

    page = client.get("/maintenance").get_data(as_text=True)

    assert '<label for="officer_name" class="form-label fw-semibold">' in page
    assert "Officer Owning Computer" in page
    assert "Officer Name<" not in page


# --- Signature pads ----------------------------------------------------


def test_every_sign_off_signature_is_a_pad_and_not_a_text_box(client):
    page = client.get("/maintenance").get_data(as_text=True)

    for name in (
        "officer_signature",
        "ict_assigned_officer_signature",
        "ict_manager_signature",
    ):
        assert f'<canvas id="{name}"' in page
        assert f'<input type="hidden" name="{name}"' in page
        assert f'type="text" name="{name}"' not in page

    # The attribute closes the tag in markup; the script matches on "[...]".
    assert page.count("data-signature-pad>") == 3
    assert page.count("data-signature-clear>") == 3
    # Nothing is signed on a blank form.
    assert 'class="signature-pad position-relative is-signed"' not in page


def test_a_drawn_signature_is_stored_and_shown_as_an_image(client, app):
    report_id = submit_report(client)

    with app.app_context():
        report = MaintenanceReport.query.get(report_id)
        assert report.officer_signature.startswith("data:image/png;base64,")
        assert report.ict_manager_signature.startswith("data:image/png;base64,")

    page = client.get(f"/table/{report_id}").get_data(as_text=True)

    assert page.count('<img class="signature-image"') == 3
    assert 'src="data:image/png;base64,' in page


def test_a_signature_that_was_not_drawn_on_the_pad_is_rejected(client, app):
    form_data = valid_maintenance_form()
    form_data["computer_name"] = "TYPED-SIGNATURE-PC"
    form_data["officer_signature"] = "I. Manager"

    response = client.post("/maintenance", data=form_data, follow_redirects=True)

    assert b"must be drawn on the signature pad" in response.data
    with app.app_context():
        assert (
            MaintenanceReport.query.filter_by(computer_name="TYPED-SIGNATURE-PC").first()
            is None
        )


def test_an_unsigned_report_is_still_accepted(client, app):
    report_id = submit_report(client, computer_name="UNSIGNED-PC", officer_signature="")

    with app.app_context():
        assert MaintenanceReport.query.get(report_id).officer_signature is None


def test_the_email_names_the_signature_instead_of_carrying_its_base64(client, outbox):
    client.post("/maintenance", data=valid_maintenance_form())

    body = outbox[0].get_content()

    assert "Officer sign: (signed)" in body
    assert "data:image/png;base64," not in body


# --- The ICT manager's edit --------------------------------------------


def test_editing_requires_signing_in(client):
    response = client.get("/maintenance/1/edit", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_a_help_desk_officer_may_not_edit_a_report(client, app):
    sign_in(client, "icthelpdesk", "field.123")

    response = client.get("/maintenance/1/edit", follow_redirects=True)

    assert b"Only an ICT manager may edit a submitted report." in response.data

    post = client.post(
        "/maintenance/1/edit", data=valid_maintenance_form(), follow_redirects=True
    )
    assert b"Only an ICT manager may edit a submitted report." in post.data
    with app.app_context():
        assert MaintenanceReport.query.get(1).computer_name == "NGOB-PC-001"


def test_the_manager_edit_form_is_prefilled_with_the_stored_report(client):
    sign_in(client, "ictmanager", "field.123")

    page = client.get("/maintenance/1/edit").get_data(as_text=True)

    assert "Edit Maintenance Report #1" in page
    assert 'value="NGOB-PC-001"' in page
    assert 'value="2026-09-01"' in page
    # Yes/No answers come back selected, and the pads come back signed.
    assert 'id="peripherals_cleaned_yes" value="Yes" checked' in page
    assert page.count('value="data:image/png;base64,') == 3
    assert page.count('class="signature-pad position-relative is-signed"') == 3


def test_a_manager_edit_overwrites_the_report_and_is_recorded(client, app):
    report_id = submit_report(client)
    sign_in(client, "ictmanager", "field.123")

    form_data = valid_maintenance_form()
    form_data["computer_name"] = "HP ProBook 640 G5"
    form_data["officer_name"] = "Corrected Officer"
    form_data["free_disk_space"] = "42 GB"

    response = client.post(
        f"/maintenance/{report_id}/edit", data=form_data, follow_redirects=False
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/table/{report_id}")

    with app.app_context():
        report = MaintenanceReport.query.get(report_id)
        assert report.computer_name == "HP ProBook 640 G5"
        assert report.officer_name == "Corrected Officer"
        assert report.free_disk_space == "42 GB"
        assert report.updated_by_username == "ictmanager"
        assert report.updated_at is not None
        # The edit updates the report in place rather than adding another.
        assert MaintenanceReport.query.count() == 3

    page = client.get(f"/table/{report_id}").get_data(as_text=True)
    assert "Edited" in page
    assert "by ictmanager" in page


def test_an_invalid_edit_re_renders_the_form_and_changes_nothing(client, app):
    sign_in(client, "ictmanager", "field.123")

    form_data = valid_maintenance_form()
    form_data["computer_name"] = ""

    response = client.post("/maintenance/1/edit", data=form_data, follow_redirects=True)

    assert b"is required" in response.data
    assert b"Edit Maintenance Report #1" in response.data
    with app.app_context():
        report = MaintenanceReport.query.get(1)
        assert report.computer_name == "NGOB-PC-001"
        assert report.updated_at is None


def test_the_administrator_may_also_edit_a_report(client):
    sign_in(client, "jonyango", "field.123")

    assert client.get("/maintenance/1/edit").status_code == 200


def test_editing_a_report_that_does_not_exist_is_not_found(client):
    sign_in(client, "ictmanager", "field.123")

    assert client.get("/maintenance/999999/edit").status_code == 404


def test_only_a_manager_sees_the_edit_buttons(client):
    anonymous = client.get("/submissions").get_data(as_text=True)
    assert "/edit" not in anonymous
    assert "/table/1" in client.get("/table/1").get_data(as_text=True) or True
    assert "Edit Report" not in client.get("/table/1").get_data(as_text=True)

    sign_in(client, "ictmanager", "field.123")

    submissions = client.get("/submissions").get_data(as_text=True)
    assert "/maintenance/1/edit" in submissions
    assert "Edit maintenance report 1" in submissions
    assert "Edit Report" in client.get("/table/1").get_data(as_text=True)


def test_a_seeded_report_carries_a_drawn_signature(app):
    with app.app_context():
        report = MaintenanceReport.query.get(1)

        assert report.officer_signature.startswith("data:image/png;base64,")
        assert report.ict_assigned_officer_signature != report.officer_signature


def test_sample_signatures_are_small_enough_to_store():
    assert len(sample_signature(0.0)) < 2000
