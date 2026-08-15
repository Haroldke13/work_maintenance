import os
import stat
import subprocess
from pathlib import Path


DEPLOY_SCRIPT = Path("deploy.sh")


def deploy_script_text():
    return DEPLOY_SCRIPT.read_text()


def test_deploy_script_exists_and_is_executable():
    assert DEPLOY_SCRIPT.exists()
    assert os.stat(DEPLOY_SCRIPT).st_mode & stat.S_IXUSR


def test_deploy_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(DEPLOY_SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_deploy_script_writes_required_environment_variables():
    script = deploy_script_text()

    for variable_name in [
        "SECRET_KEY",
        "ADMIN_USERNAME",
        "ADMIN_PASSWORD",
        "DEFAULT_USER_PASSWORD",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_HOST_PORT",
        "DATABASE_URL",
    ]:
        assert f"{variable_name}=" in script


def test_deploy_script_creates_database_role_and_database():
    script = deploy_script_text()

    assert "CREATE ROLE" in script
    assert "ALTER ROLE" in script
    assert "CREATE DATABASE" in script
    assert "ALTER DATABASE" in script
    assert "pg_database" in script
    assert "pg_roles" in script


def test_deploy_script_runs_migrations_before_seed_data():
    script = deploy_script_text()

    migrate_command = "db upgrade"
    seed_command = "seed-data"

    assert migrate_command in script
    assert seed_command in script
    assert script.index(migrate_command) < script.index(seed_command)
