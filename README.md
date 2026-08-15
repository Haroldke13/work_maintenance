# ICT Cleanup Practical Flask App

This Flask application converts `Windows Computer Clean-Up and Virtual Memory Practical.docx` into a PostgreSQL-backed form workflow.

## What It Includes

- `cleanup.html`: the practical form.
- `table.html`: a Bootstrap DataTable for one submitted record.
- `admin.html`: admin login and user creation.
- `templates/all records.html`: admin-only Bootstrap DataTable for every submitted record and every captured field.
- `models.py`: SQLAlchemy models for users and cleanup records.
- Docker and Docker Compose files for Flask plus PostgreSQL.

## Default Admin

- Username: `jonyango`
- Password: `field.123`

The admin can create users from `/admin`. New user passwords auto-set to `field.123`.

## Run With Docker

```bash
docker compose up --build
```

Open:

- Form: `http://localhost:5000/cleanup`
- Admin: `http://localhost:5000/admin`
- Admin records: `http://localhost:5000/admin/records`

The `db` service creates the PostgreSQL database from `.env`. The web container runs `flask --app 'app:create_app()' db upgrade` and then `flask --app 'app:create_app()' seed-data` before starting Gunicorn, so migrations, the `jonyango` admin, and the first two seed records are applied automatically.

PostgreSQL is exposed on host port `5433` by default through `POSTGRES_HOST_PORT` to avoid clashing with an existing local PostgreSQL service. Containers still connect internally through `db:5432`.

## Run Without Docker

Install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start PostgreSQL locally and ensure `.env` contains a working `DATABASE_URL`. If using the Compose database from the host, use `POSTGRES_HOST_PORT`, which defaults to `5433`. Then run:

```bash
flask --app 'app:create_app()' db upgrade
flask --app 'app:create_app()' seed-data
flask --app 'app:create_app()' run --host 0.0.0.0 --port 5000
```

## Server Deploy Without Docker

Use this when PostgreSQL is already installed on the server:

```bash
chmod +x deploy.sh
./deploy.sh
```

The script:

- creates or updates `.env`;
- creates the PostgreSQL login role from `POSTGRES_USER` and `POSTGRES_PASSWORD`;
- creates the PostgreSQL database from `POSTGRES_DB`;
- writes `DATABASE_URL`;
- creates/updates `.venv` and installs `requirements.txt`;
- runs `flask db upgrade` to create/update tables;
- runs `seed-data` to create the admin user and first two records.

If the server does not allow the current shell user to administer PostgreSQL, provide an admin login:

```bash
POSTGRES_ADMIN_USER=postgres POSTGRES_ADMIN_PASSWORD='admin-password' ./deploy.sh
```

To start Gunicorn immediately after setup:

```bash
RUN_SERVER=1 APP_PORT=5000 ./deploy.sh
```

## Database Migrations

This app uses Flask-Migrate/Alembic. Keep model changes and migration files together:

```bash
flask --app 'app:create_app()' db migrate -m "describe schema change"
flask --app 'app:create_app()' db upgrade
```

For a database that was already created before migrations were added, stamp it once after confirming the schema matches the baseline:

```bash
flask --app 'app:create_app()' db stamp head
```

## Production Notes

- Replace `SECRET_KEY`, `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, and `DEFAULT_USER_PASSWORD` in production.
- Keep production secrets in environment variables or a protected `.env` file.
- Any production platform that provides `DATABASE_URL` can override the local `.env` value.
- Production startup should run `flask db upgrade` before `seed-data`, matching `entrypoint.sh`.
