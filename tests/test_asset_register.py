"""The ICT Computer Register, and the serial-number lookup that prefills the form."""

import re

import pytest

from conftest import sign_in, sign_out

from asset_register import MIN_QUERY_LENGTH, read_register, search_assets
from models import ComputerAsset, MaintenanceReport


@pytest.fixture(autouse=True)
def signed_in(client):
    """The portal is gated. These tests are about its pages, not its door."""
    sign_in(client, "icthelpdesk", "field.123")


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


def test_the_register_page_lists_the_three_columns_and_every_computer(client, app):
    from asset_register import only_computers

    response = client.get("/assets")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Computer Register" in page
    for heading in ("Serial number", "Make &amp; Model", "Responsible officer"):
        assert heading in page

    with app.app_context():
        # The page starts maintenance reports, so it carries the computers on
        # the register rather than all of its lines.
        total = only_computers(ComputerAsset.query).count()

    assert f"{total} assets" in page
    # Every computer has a row of its own, across all the branch tables.
    body_rows = sum(
        chunk.split("</tbody>")[0].count("<tr>")
        for chunk in page.split("<tbody>")[1:]
    )
    assert body_rows == total


def test_the_register_page_is_behind_the_sign_in(client):
    sign_out(client)

    response = client.get("/assets", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


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


# --- Only computers reach the page that starts a report ------------------


def test_the_register_page_lists_only_computers_and_laptops(client, app):
    from asset_register import is_computer

    page = client.get("/assets").get_data(as_text=True)

    with app.app_context():
        computers = [a for a in ComputerAsset.query.all() if is_computer(a.asset_description)]
        others = [a for a in ComputerAsset.query.all() if not is_computer(a.asset_description)]

    assert computers and others, "the register should hold both"
    assert f"{len(computers)} assets" in page
    # The counted total is the sieved one, not the whole register.
    assert str(len(computers) + len(others)) + " assets" not in page


def test_telephones_printers_and_the_air_con_are_sieved_out(client, app):
    with app.app_context():
        excluded = (
            ComputerAsset.query.filter(
                ComputerAsset.asset_description.in_(
                    ["TELEPHONE HEADS", "PRINTER/COPIER", "AIR CON", "PAPER SHREDDER"]
                )
            )
            .filter(ComputerAsset.serial_no.isnot(None), ComputerAsset.serial_no != "")
            .all()
        )
        serials = [a.serial_no for a in excluded]

    assert serials, "the register should carry non-computers"
    page = client.get("/assets").get_data(as_text=True)

    for serial in serials:
        assert serial not in page, serial


def test_both_computer_descriptions_survive_the_sieve(app):
    from asset_register import only_computers

    with app.app_context():
        kept = {a.asset_description for a in only_computers(ComputerAsset.query).all()}

    assert kept == {"CPU / Monitor / Keyboard", "LAPTOP COMPUTER"}


def test_the_sieve_is_case_and_whitespace_insensitive():
    from asset_register import is_computer

    assert is_computer("  LAPTOP COMPUTER  ")
    assert is_computer("cpu / monitor / keyboard")
    assert is_computer("CPU / Monitor / Keyboard")
    assert not is_computer("TELEPHONE HEADS")
    assert not is_computer("")
    assert not is_computer(None)


def test_the_full_register_is_still_there_for_the_administrator(client, app):
    """Sieving the officer's page must not hide lines from the asset register."""
    sign_in(client, "jonyango", "field.123")

    page = client.get("/admin/assets").get_data(as_text=True)

    assert "TELEPHONE HEADS" in page
    with app.app_context():
        assert ComputerAsset.query.count() == len(read_register())


# --- Branches ------------------------------------------------------------


def accordion_headings(page: str) -> list[tuple[str, str]]:
    """The (branch, count) label of every accordion button, in page order."""
    return [
        (branch.strip(), count.strip())
        for branch, count in re.findall(
            r'aria-controls="branch-\d+">\s*(.*?)\s*<span[^>]*>\s*(.*?)\s*</span>',
            page,
            re.S,
        )
    ]


def test_the_register_is_stratified_into_one_accordion_per_branch(client, app):
    from asset_register import computers_by_branch

    page = client.get("/assets").get_data(as_text=True)

    with app.app_context():
        branches = computers_by_branch()

    headings = accordion_headings(page)

    assert len(branches) > 1
    assert f"{len(branches)} branches" in page
    assert headings == [
        (branch, f"{len(assets)} computer{'' if len(assets) == 1 else 's'}")
        for branch, assets in branches
    ]


def test_nairobi_is_the_first_accordion_and_the_only_one_open(client):
    page = client.get("/assets").get_data(as_text=True)

    headings = accordion_headings(page)

    assert headings[0][0] == "Nairobi"
    # Exactly one panel arrives expanded, and it is Nairobi's.
    assert page.count("accordion-collapse collapse show") == 1
    assert page.index("collapse show") < page.index("accordion-button collapsed")
    assert page.count('aria-expanded="true"') == 1


def test_a_branch_table_holds_exactly_its_own_machines(client, app):
    """The rows under a heading are that branch's, not the next one's."""
    from asset_register import computers_by_branch

    page = client.get("/assets").get_data(as_text=True)
    panels = page.split('class="accordion-item panel"')[1:]

    with app.app_context():
        branches = computers_by_branch()

    assert len(panels) == len(branches)
    for panel, (branch, assets) in zip(panels, branches):
        rows = panel.split("<tbody>")[1].split("</tbody>")[0]
        assert rows.count("<tr>") == len(assets), branch
        for asset in assets:
            if asset.serial_no:
                assert asset.serial_no in rows, f"{asset.serial_no} missing from {branch}"


def test_every_branch_after_nairobi_is_in_alphabetical_order(app):
    from asset_register import computers_by_branch

    with app.app_context():
        names = [branch for branch, _ in computers_by_branch()]

    assert names[0] == "Nairobi"
    assert names[1:] == sorted(names[1:])


def test_each_machine_appears_under_its_own_branch(client, app):
    from asset_register import branch_of, computers_by_branch

    with app.app_context():
        for branch, assets in computers_by_branch():
            for asset in assets:
                assert branch_of(asset.location) == branch


def test_branch_names_are_folded_so_one_office_is_one_accordion():
    from asset_register import branch_of

    # The workbook spells these two more than one way.
    assert branch_of("NAKURU") == branch_of("Nakuru") == "Nakuru"
    assert branch_of("Garisa") == branch_of("Garissa") == "Garissa"
    assert branch_of("nairobi") == "Nairobi"


def test_a_machine_with_no_location_still_gets_a_home():
    from asset_register import NO_BRANCH, branch_of

    assert branch_of("") == NO_BRANCH
    assert branch_of(None) == NO_BRANCH
    assert branch_of("   ") == NO_BRANCH


def test_a_branchless_machine_sorts_last(app):
    from asset_register import NO_BRANCH, _branch_order

    names = ["Nairobi", "Mombasa", NO_BRANCH, "Eldoret"]

    assert sorted(names, key=_branch_order) == ["Nairobi", "Eldoret", "Mombasa", NO_BRANCH]


def test_the_branch_totals_add_up_to_the_page_total(client, app):
    from asset_register import computers_by_branch, only_computers

    with app.app_context():
        branches = computers_by_branch()
        assert sum(len(a) for _, a in branches) == only_computers(ComputerAsset.query).count()


def test_an_officer_link_still_starts_a_report_from_inside_a_branch(client, app):
    with app.app_context():
        asset_id = ComputerAsset.query.filter_by(serial_no="CZ018C7P").one().id

    page = client.get("/assets").get_data(as_text=True)

    assert f'href="/maintenance?asset={asset_id}"' in page
    assert client.get(f"/maintenance?asset={asset_id}").status_code == 200
