from form_schema import blank_form_data
from models import CleanupRecord, User


def valid_cleanup_form():
    form_data = blank_form_data()
    form_data.update(
        {
            "intern_name": "Route Coverage Intern",
            "computer_name": "ROUTE-PC",
            "practical_date": "2026-07-27",
            "supervisor": "jonyango",
            "system_type": "64-bit",
            "computer_info_recorded": True,
        }
    )
    return form_data


def login_admin(client):
    return client.post(
        "/admin",
        data={"action": "login", "username": "jonyango", "password": "field.123"},
        follow_redirects=True,
    )


def test_seeded_admin_and_initial_records(app):
    with app.app_context():
        admin_user = User.query.filter_by(username="jonyango", is_admin=True).one()

        assert admin_user.check_password("field.123")
        assert CleanupRecord.query.count() == 2


def test_index_redirects_to_cleanup(client):
    response = client.get("/")

    assert response.status_code == 302
    assert "/cleanup" in response.headers["Location"]


def test_cleanup_get_renders_form(client):
    response = client.get("/cleanup")

    assert response.status_code == 200
    assert b"Windows Computer Clean-Up" in response.data


def test_cleanup_post_invalid_rerenders_required_errors(client):
    response = client.post("/cleanup", data={}, follow_redirects=True)

    assert response.status_code == 200
    assert b"is required" in response.data


def test_cleanup_post_valid_creates_record_and_redirects_to_table(client):
    response = client.post("/cleanup", data=valid_cleanup_form(), follow_redirects=False)

    assert response.status_code == 302
    assert "/table/" in response.headers["Location"]

    table_response = client.get(response.headers["Location"])
    assert table_response.status_code == 200
    assert b"Route Coverage Intern" in table_response.data
    assert b"recordTable" in table_response.data


def test_missing_table_record_returns_404(client):
    response = client.get("/table/999999")

    assert response.status_code == 404


def test_admin_get_renders_login_when_logged_out(client):
    response = client.get("/admin")

    assert response.status_code == 200
    assert b"Admin Login" in response.data


def test_admin_rejects_wrong_password(client):
    response = client.post(
        "/admin",
        data={"action": "login", "username": "jonyango", "password": "wrong"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Invalid admin username or password" in response.data


def test_admin_records_redirects_when_logged_out(client):
    response = client.get("/admin/records", follow_redirects=False)

    assert response.status_code == 302
    assert "/admin" in response.headers["Location"]


def test_admin_login_create_user_and_view_all_records(client, app):
    login_response = login_admin(client)

    assert login_response.status_code == 200
    assert b"Admin Dashboard" in login_response.data

    create_response = client.post(
        "/admin",
        data={"action": "create_user", "username": "intern_a"},
        follow_redirects=True,
    )

    assert create_response.status_code == 200
    assert b"intern_a" in create_response.data

    with app.app_context():
        new_user = User.query.filter_by(username="intern_a").one()
        assert new_user.check_password("field.123")
        assert new_user.created_by == "jonyango"

    duplicate_response = client.post(
        "/admin",
        data={"action": "create_user", "username": "intern_a"},
        follow_redirects=True,
    )

    assert duplicate_response.status_code == 200
    assert b"already exists" in duplicate_response.data

    client.post("/cleanup", data=valid_cleanup_form(), follow_redirects=False)
    records_response = client.get("/admin/records")

    assert records_response.status_code == 200
    assert b"allRecordsTable" in records_response.data
    assert b"Route Coverage Intern" in records_response.data


def test_admin_logout_returns_to_login(client):
    login_admin(client)
    response = client.post("/admin/logout", follow_redirects=True)

    assert response.status_code == 200
    assert b"Admin Login" in response.data


def test_static_missing_asset_returns_404(client):
    response = client.get("/static/not-found.css")

    assert response.status_code == 404
