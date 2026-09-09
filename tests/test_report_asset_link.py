"""The foreign key tying a maintenance report to its line on the computer register."""

from conftest import sign_in
from test_routes import valid_maintenance_form

from models import ComputerAsset, MaintenanceReport


def asset_for(app, serial="CZ018C7P"):
    with app.app_context():
        asset = ComputerAsset.query.filter_by(serial_no=serial).one()
        return asset.id, asset.responsible_officer, asset.make_model


def submit(client, **overrides):
    form_data = valid_maintenance_form()
    form_data.update(overrides)
    response = client.post("/maintenance", data=form_data, follow_redirects=False)
    return int(response.headers["Location"].rsplit("/", 1)[1])


def test_a_report_started_from_the_register_is_linked_by_id(client, app):
    asset_id, officer, model = asset_for(app)

    report_id = submit(
        client,
        asset_id=str(asset_id),
        serial_no="CZ018C7P",
        computer_name=model,
        officer_name=officer,
    )

    with app.app_context():
        report = MaintenanceReport.query.get(report_id)
        assert report.asset_id == asset_id
        assert report.asset.responsible_officer == officer


def test_a_typed_serial_still_links_to_the_register(client, app):
    asset_id, _, _ = asset_for(app)

    # No asset_id posted at all — the serial number alone must resolve.
    report_id = submit(client, serial_no="CZ018C7P")

    with app.app_context():
        assert MaintenanceReport.query.get(report_id).asset_id == asset_id


def test_serial_matching_ignores_case_and_padding(client, app):
    asset_id, _, _ = asset_for(app)

    report_id = submit(client, serial_no="  cz018c7p  ")

    with app.app_context():
        assert MaintenanceReport.query.get(report_id).asset_id == asset_id


def test_a_machine_not_on_the_register_leaves_the_link_empty(client, app):
    report_id = submit(client, serial_no="NOT-ON-THE-REGISTER-1")

    with app.app_context():
        report = MaintenanceReport.query.get(report_id)
        assert report.asset_id is None
        assert report.asset is None
        # The report is still perfectly valid without a register line.
        assert report.serial_no == "NOT-ON-THE-REGISTER-1"


def test_a_report_with_no_serial_is_unlinked(client, app):
    report_id = submit(client, serial_no="")

    with app.app_context():
        assert MaintenanceReport.query.get(report_id).asset_id is None


def test_a_bogus_asset_id_falls_back_to_the_serial(client, app):
    asset_id, _, _ = asset_for(app)

    report_id = submit(client, asset_id="999999", serial_no="CZ018C7P")

    with app.app_context():
        assert MaintenanceReport.query.get(report_id).asset_id == asset_id


def test_a_junk_asset_id_does_not_break_the_post(client, app):
    report_id = submit(client, asset_id="../../etc/passwd", serial_no="CZ018C7P")

    with app.app_context():
        assert MaintenanceReport.query.get(report_id).asset_id is not None


def test_the_prefilled_form_carries_the_link_in_a_hidden_field(client, app):
    asset_id, _, _ = asset_for(app)

    page = client.get(f"/maintenance?asset={asset_id}").get_data(as_text=True)

    assert f'name="asset_id" value="{asset_id}"' in page


def test_a_blank_form_carries_an_empty_link(client):
    page = client.get("/maintenance").get_data(as_text=True)

    assert 'name="asset_id" value=""' in page


def test_the_report_page_names_the_register_entry(client, app):
    report_id = submit(client, serial_no="CZ018C7P")

    page = client.get(f"/table/{report_id}").get_data(as_text=True)

    assert "Register entry" in page
    assert "CPU / Monitor / Keyboard" in page
    assert "NGOB/02/0230" in page


def test_an_unlinked_report_shows_no_register_entry(client):
    report_id = submit(client, serial_no="NOT-ON-THE-REGISTER-2")

    page = client.get(f"/table/{report_id}").get_data(as_text=True)

    assert "Register entry" not in page


def test_a_manager_edit_moves_the_link_with_the_serial(client, app):
    report_id = submit(client, serial_no="CZ018C7P")
    sign_in(client, "ictmanager", "field.123")

    with app.app_context():
        moved_to = ComputerAsset.query.filter_by(serial_no="CZC018C2FS").one().id

    form_data = valid_maintenance_form()
    form_data["serial_no"] = "CZC018C2FS"
    form_data["asset_id"] = ""
    client.post(f"/maintenance/{report_id}/edit", data=form_data)

    with app.app_context():
        assert MaintenanceReport.query.get(report_id).asset_id == moved_to


def test_an_edit_to_an_unregistered_serial_clears_the_link(client, app):
    report_id = submit(client, serial_no="CZ018C7P")
    sign_in(client, "ictmanager", "field.123")

    form_data = valid_maintenance_form()
    form_data["serial_no"] = "GONE-FROM-THE-REGISTER"
    form_data["asset_id"] = ""
    client.post(f"/maintenance/{report_id}/edit", data=form_data)

    with app.app_context():
        assert MaintenanceReport.query.get(report_id).asset_id is None


def test_the_register_line_can_reach_its_reports(client, app):
    asset_id, _, _ = asset_for(app)
    submit(client, serial_no="CZ018C7P")
    submit(client, serial_no="CZ018C7P")

    with app.app_context():
        asset = ComputerAsset.query.get(asset_id)
        assert len(asset.reports) == 2
        assert {r.serial_no for r in asset.reports} == {"CZ018C7P"}
