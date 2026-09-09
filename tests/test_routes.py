from datetime import date, time

from conftest import create_user, sign_in

from models import MaintenanceReport, User
from seed_data import sample_signature


def valid_maintenance_form():
    """A complete post, with the three signatures as the pad's PNG data URLs."""
    return {
        "serial_no": "NGOB/ICT/104b/9001",
        "computer_name": "ROUTE-PC",
        "department": "ICT Department",
        "officer_name": "Route Coverage Officer",
        "report_time": "09:45",
        "report_date": "2026-09-01",
        "peripherals_cleaned": "Yes",
        "data_backup_schedule_status": "Weekly backup verified.",
        "windows_firewall_status": "Enabled on all profiles.",
        "allowed_firewall_exceptions": "Core Networking\nRemote Desktop",
        "windows_update_status": "Up to date.",
        "unneeded_running_services": "Fax",
        "autoruns": "OneDrive",
        "unneeded_software": "Trial PDF editor",
        "antivirus_auto_protect_status": "Active.",
        "last_antivirus_update": "2026-08-31",
        "windows_user_accounts": "Administrator",
        "disk_defragmentation_done": "No",
        "free_disk_space": "118 GB",
        "other_observations": "No further issues.",
        "officer_sign_name": "Route Coverage Officer",
        "officer_signature": sample_signature(0.3),
        "officer_sign_date": "2026-09-01",
        "ict_assigned_officer_name": "jonyango",
        "ict_assigned_officer_signature": sample_signature(0.9),
        "ict_assigned_officer_sign_date": "2026-09-01",
        "ict_manager_name": "ICT Manager",
        "ict_manager_signature": sample_signature(1.6),
        "ict_manager_sign_date": "2026-09-02",
    }


def login_admin(client):
    return sign_in(client, "jonyango", "field.123")


def test_seeded_admin_and_initial_reports(app):
    with app.app_context():
        admin_user = User.query.filter_by(username="jonyango", is_admin=True).one()

        assert admin_user.check_password("field.123")
        assert MaintenanceReport.query.count() == 2


def test_index_redirects_to_maintenance(client):
    response = client.get("/")

    assert response.status_code == 302
    assert "/maintenance" in response.headers["Location"]


def test_maintenance_get_renders_form(client):
    response = client.get("/maintenance")

    assert response.status_code == 200
    assert b"Computer Maintenance Report (NGOB/ICT/104b)" in response.data
    assert b"14. Any other observation made on computer" in response.data


def test_maintenance_post_invalid_rerenders_required_errors(client):
    response = client.post("/maintenance", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"is required" in response.data


def test_maintenance_post_rejects_malformed_date(client):
    form_data = valid_maintenance_form()
    form_data["last_antivirus_update"] = "31-08-2026"

    response = client.post("/maintenance", data=form_data, follow_redirects=True)

    assert response.status_code == 200
    assert b"must be a valid date" in response.data


def test_maintenance_post_valid_creates_typed_report(client, app):
    response = client.post("/maintenance", data=valid_maintenance_form(), follow_redirects=False)

    assert response.status_code == 302
    assert "/table/" in response.headers["Location"]

    with app.app_context():
        report = MaintenanceReport.query.filter_by(computer_name="ROUTE-PC").one()

        assert report.report_date == date(2026, 9, 1)
        assert report.report_time == time(9, 45)
        assert report.last_antivirus_update == date(2026, 8, 31)
        assert report.peripherals_cleaned is True
        assert report.disk_defragmentation_done is False
        assert report.allowed_firewall_exceptions == "Core Networking\nRemote Desktop"

    table_response = client.get(response.headers["Location"])
    assert table_response.status_code == 200
    assert b"Route Coverage Officer" in table_response.data
    assert b"recordTable" in table_response.data


def test_unanswered_yes_no_question_is_stored_as_null(client, app):
    form_data = valid_maintenance_form()
    form_data.pop("peripherals_cleaned")
    form_data["computer_name"] = "UNANSWERED-PC"

    client.post("/maintenance", data=form_data, follow_redirects=False)

    with app.app_context():
        report = MaintenanceReport.query.filter_by(computer_name="UNANSWERED-PC").one()

        assert report.peripherals_cleaned is None


def test_missing_table_report_returns_404(client):
    response = client.get("/table/999999")

    assert response.status_code == 404


def test_admin_redirects_to_the_shared_sign_in_when_logged_out(client):
    response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_sign_in_rejects_wrong_password(client):
    response = sign_in(client, "jonyango", "wrong")

    assert response.status_code == 200
    assert b"Invalid username or password" in response.data


def test_admin_records_redirects_when_logged_out(client):
    response = client.get("/admin/records", follow_redirects=False)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_sign_in_sends_each_account_to_its_own_area(client):
    admin_landing = sign_in(client, "jonyango", "field.123")
    assert b"Admin Dashboard" in admin_landing.data

    client.post("/logout")
    officer_landing = sign_in(client, "icthelpdesk", "field.123")
    assert b"Help Desk Dashboard" in officer_landing.data


def test_admin_login_create_user_and_view_all_reports(client, app):
    login_response = login_admin(client)

    assert login_response.status_code == 200
    assert b"Admin Dashboard" in login_response.data

    create_response = create_user(client, "intern_a")

    assert create_response.status_code == 200
    assert b"intern_a" in create_response.data

    with app.app_context():
        new_user = User.query.filter_by(username="intern_a").one()
        assert new_user.check_password("field.123")
        assert new_user.created_by == "jonyango"
        assert new_user.helpdesk_role is None

    duplicate_response = create_user(client, "intern_a")

    assert duplicate_response.status_code == 200
    assert b"already exists" in duplicate_response.data

    client.post("/maintenance", data=valid_maintenance_form(), follow_redirects=False)
    records_response = client.get("/admin/records")

    assert records_response.status_code == 200
    assert b"allRecordsTable" in records_response.data
    assert b"Route Coverage Officer" in records_response.data


def test_admin_can_grant_help_desk_access_when_creating_a_user(client, app):
    login_admin(client)

    create_user(client, "desk_officer", full_name="Desk Officer", helpdesk_role="officer")

    with app.app_context():
        created = User.query.filter_by(username="desk_officer").one()
        assert created.helpdesk_role == "officer"
        assert created.is_helpdesk_staff
        assert created.is_manager is False
        assert created.check_password("field.123")

    rejected = create_user(client, "bad_role", helpdesk_role="superuser")

    assert b"Choose a valid help desk role" in rejected.data
    with app.app_context():
        assert User.query.filter_by(username="bad_role").first() is None


def test_the_new_account_can_sign_in_and_work_the_help_desk(client, app):
    login_admin(client)
    create_user(client, "desk_officer", full_name="Desk Officer", helpdesk_role="officer")
    client.post("/logout")

    landing = sign_in(client, "desk_officer", "field.123")

    assert b"Help Desk Dashboard" in landing.data
    # A help desk officer is still not an administrator.
    assert client.get("/admin", follow_redirects=False).status_code == 302


def test_logout_returns_to_the_shared_sign_in(client):
    login_admin(client)
    response = client.post("/logout", follow_redirects=True)

    assert response.status_code == 200
    assert b"Sign In" in response.data


def test_static_missing_asset_returns_404(client):
    response = client.get("/static/not-found.css")

    assert response.status_code == 404


def test_maintenance_form_links_to_the_help_desk(client):
    response = client.get("/maintenance")

    assert response.status_code == 200
    assert b"Report a Problem to the Help Desk" in response.data
    assert b'href="/helpdesk/"' in response.data


def test_admin_can_set_an_email_when_creating_a_user(client, app):
    login_admin(client)

    create_user(client, "desk_two", full_name="Desk Two",
                email="desk.two@pbora.go.ke", helpdesk_role="officer")

    with app.app_context():
        created = User.query.filter_by(username="desk_two").one()
        assert created.email == "desk.two@pbora.go.ke"


def test_submissions_page_lists_every_report_with_a_detail_button(client):
    client.post("/maintenance", data=valid_maintenance_form(), follow_redirects=False)

    response = client.get("/submissions")

    assert response.status_code == 200
    assert b"submissionsTable" in response.data
    assert b"All Submissions" in response.data
    assert b"ROUTE-PC" in response.data
    # The seeded pair plus the report submitted above, each with a View button.
    assert response.data.count(b"View maintenance report") == 3


def test_submissions_detail_button_links_to_the_report_page(client):
    post_response = client.post(
        "/maintenance", data=valid_maintenance_form(), follow_redirects=False
    )
    report_path = post_response.headers["Location"]

    response = client.get("/submissions")

    assert f'href="{report_path}"'.encode() in response.data
    assert client.get(report_path).status_code == 200


def test_submissions_view_button_is_the_first_column(client):
    response = client.get("/submissions")
    body = response.get_data(as_text=True)

    header = body[body.index("<thead>") : body.index("</thead>")]
    first_row = body[body.index("<tbody>") : body.index("</tr>", body.index("<tbody>"))]

    assert header.index("View") < header.index("ID")
    assert "btn-view" in first_row.split("</td>")[0]


def test_all_records_table_has_a_detail_button_in_the_first_column(client):
    login_admin(client)
    client.post("/maintenance", data=valid_maintenance_form(), follow_redirects=False)

    response = client.get("/admin/records")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    header = body[body.index("<thead>") : body.index("</thead>")]
    first_row = body[body.index("<tbody>") : body.index("</tr>", body.index("<tbody>"))]

    assert header.index("View") < header.index("ID")
    assert "btn-view" in first_row.split("</td>")[0]


def test_submissions_page_is_reachable_from_the_form(client):
    response = client.get("/maintenance")

    assert b'href="/submissions"' in response.data
