"""The ICT Computer Register, and the serial-number lookup that prefills the form."""

from conftest import sign_in

from asset_register import MIN_QUERY_LENGTH, read_register, search_assets
from models import ComputerAsset, MaintenanceReport


def test_the_register_csv_carries_the_organisations_assets():
    entries = read_register()

    assert len(entries) > 150
    # Every line is at least identifiable by one of the three recorded columns.
    for entry in entries:
        assert entry["serial_no"] or entry["make_model"] or entry["responsible_officer"]


def test_the_register_is_loaded_into_the_database(app):
    with app.app_context():
        assert ComputerAsset.query.count() == len(read_register())

        asset = ComputerAsset.query.filter_by(serial_no="CZ018C7P").one()
        assert asset.responsible_officer == "David Njane"
        assert asset.make_model.startswith("HP PRODESK")
        assert "NGOB/02/0230" in asset.tag_numbers


def test_seeding_twice_does_not_duplicate_the_register(app):
    with app.app_context():
        before = ComputerAsset.query.count()

    app.test_cli_runner().invoke(args=["seed-data"])

    with app.app_context():
        assert ComputerAsset.query.count() == before


def test_three_characters_are_needed_before_the_register_is_searched(app):
    with app.app_context():
        assert MIN_QUERY_LENGTH == 3
        assert search_assets("CZ") == []
        assert search_assets("") == []
        assert len(search_assets("CZ0")) > 0


def test_a_serial_prefix_finds_the_machine_it_belongs_to(app):
    with app.app_context():
        matches = search_assets("CZ018C7")

        assert matches
        assert matches[0].serial_no == "CZ018C7P"
        assert matches[0].responsible_officer == "David Njane"


def test_the_search_is_case_insensitive(app):
    with app.app_context():
        assert [a.serial_no for a in search_assets("cz018c7")] == [
            a.serial_no for a in search_assets("CZ018C7")
        ]


def test_a_monitors_serial_finds_its_computer(app):
    with app.app_context():
        matches = search_assets("3CQ0030ZLZ")

        assert matches
        assert matches[0].serial_no == "CZ018C7P"


def test_the_lookup_endpoint_returns_suggestions_as_json(client):
    response = client.get("/assets/lookup?q=CZ018C7")

    assert response.status_code == 200
    payload = response.get_json()

    assert payload
    first = payload[0]
    assert first["serial_no"] == "CZ018C7P"
    assert first["responsible_officer"] == "David Njane"
    assert first["make_model"].startswith("HP PRODESK")


def test_the_lookup_endpoint_is_quiet_below_three_characters(client):
    assert client.get("/assets/lookup?q=CZ").get_json() == []
    assert client.get("/assets/lookup").get_json() == []


def test_the_lookup_returns_a_short_list_a_dropdown_can_show(client):
    payload = client.get("/assets/lookup?q=CZC").get_json()

    assert 0 < len(payload) <= 12


def test_the_form_wires_the_serial_field_to_the_lookup(client):
    page = client.get("/maintenance").get_data(as_text=True)

    assert 'data-lookup-url="/assets/lookup"' in page
    assert 'name="serial_no"' in page and "data-asset-input" in page
    assert 'id="serial_no_suggestions"' in page
    # The two fields the pick fills in.
    assert 'id="computer_name"' in page
    assert 'id="officer_name"' in page


def test_the_admin_asset_register_page_lists_the_assets(client, app):
    sign_in(client, "jonyango", "field.123")

    response = client.get("/admin/assets")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "ICT Computer Register" in page
    assert "CZ018C7P" in page
    assert "David Njane" in page
    with app.app_context():
        assert f"{ComputerAsset.query.count()} assets" in page


def test_the_asset_register_page_is_admin_only(client):
    response = client.get("/admin/assets", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_the_admin_dashboard_counts_the_registered_computers(client, app):
    sign_in(client, "jonyango", "field.123")

    page = client.get("/admin").get_data(as_text=True)

    with app.app_context():
        assert f"Asset Register ({ComputerAsset.query.count()})" in page
    assert "Registered computers" in page


# --- The Computer Register page ----------------------------------------


def test_the_register_page_lists_the_three_columns_and_every_row(client, app):
    response = client.get("/assets")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Computer Register" in page
    for heading in ("Serial number", "Make &amp; Model", "Responsible officer"):
        assert heading in page

    with app.app_context():
        total = ComputerAsset.query.count()
        assert f"{total} assets" in page
        # Every register line has a row of its own.
        body = page[page.index("<tbody>"):page.index("</tbody>")]
        assert body.count("<tr>") == total


def test_the_register_page_needs_no_sign_in(client):
    assert client.get("/assets", follow_redirects=False).status_code == 200


def test_an_officer_name_links_to_the_report_form(client, app):
    with app.app_context():
        asset = ComputerAsset.query.filter_by(serial_no="CZ018C7P").one()
        asset_id = asset.id

    page = client.get("/assets").get_data(as_text=True)

    assert f'href="/maintenance?asset={asset_id}"' in page
    assert "David Njane" in page


def test_clicking_an_officer_opens_a_prefilled_report_form(client, app):
    with app.app_context():
        asset_id = ComputerAsset.query.filter_by(serial_no="CZ018C7P").one().id

    response = client.get(f"/maintenance?asset={asset_id}")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'value="CZ018C7P"' in page
    assert 'value="David Njane"' in page
    assert "HP PRODESK" in page
    assert "Filled in from the Computer Register." in page


def test_a_prefilled_form_still_submits_as_a_normal_report(client, app):
    from test_routes import valid_maintenance_form

    with app.app_context():
        asset_id = ComputerAsset.query.filter_by(serial_no="CZ018C7P").one().id

    client.get(f"/maintenance?asset={asset_id}")

    form_data = valid_maintenance_form()
    form_data.update({
        "serial_no": "CZ018C7P",
        "computer_name": "HP PRODESK",
        "officer_name": "David Njane",
    })
    response = client.post("/maintenance", data=form_data, follow_redirects=False)

    assert response.status_code == 302
    with app.app_context():
        report = MaintenanceReport.query.filter_by(serial_no="CZ018C7P").one()
        assert report.officer_name == "David Njane"


def test_an_unknown_or_junk_asset_id_just_gives_a_blank_form(client):
    for suffix in ("?asset=999999", "?asset=abc", "?asset=", ""):
        response = client.get(f"/maintenance{suffix}")

        assert response.status_code == 200
        page = response.get_data(as_text=True)
        assert "Filled in from the Computer Register." not in page
        assert 'id="serial_no"' in page


def test_every_page_carries_the_register_button(client):
    for path in ("/maintenance", "/submissions", "/scripts", "/assets"):
        page = client.get(path).get_data(as_text=True)

        assert 'href="/assets"' in page, path
        assert "Computer Register" in page, path


def test_rows_an_officer_can_act_on_come_first(client):
    page = client.get("/assets").get_data(as_text=True)
    body = page[page.index("<tbody>"):page.index("</tbody>")]
    rows = body.split("<tr>")[1:]

    first_unassigned = next(i for i, row in enumerate(rows) if "officer-link" not in row)
    last_assigned = max(i for i, row in enumerate(rows) if "officer-link" in row)

    assert first_unassigned > last_assigned
