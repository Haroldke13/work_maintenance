from pathlib import Path

from models import CleanupRecord


def test_flask_migrate_db_command_is_registered(app):
    result = app.test_cli_runner().invoke(args=["db", "--help"])

    assert result.exit_code == 0
    assert "upgrade" in result.output
    assert "migrate" in result.output


def test_seed_data_command_is_idempotent(app):
    runner = app.test_cli_runner()

    with app.app_context():
        before_count = CleanupRecord.query.count()

    result = runner.invoke(args=["seed-data"])

    assert result.exit_code == 0
    with app.app_context():
        assert CleanupRecord.query.count() == before_count


def test_entrypoint_runs_migrations_before_seed_data():
    lines = Path("entrypoint.sh").read_text().splitlines()

    migrate_line = "flask --app 'app:create_app()' db upgrade"
    seed_line = "flask --app 'app:create_app()' seed-data"

    assert migrate_line in lines
    assert seed_line in lines
    assert lines.index(migrate_line) < lines.index(seed_line)
