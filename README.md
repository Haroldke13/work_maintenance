# PBO Regulatory Authority Computer Maintenance Report Flask App

This Flask application turns the Public Benefit Organizations Regulatory Authority **Computer Maintenance Report (NGOB/ICT/104b)** paper form into a PostgreSQL-backed workflow. Every question on the form is a real, typed column on the `maintenance_reports` table.

## What It Includes

- `maintenance.html`: the NGOB/ICT/104b maintenance report form.
- `table.html`: a Bootstrap DataTable for one submitted report.
- `admin.html`: admin login and user creation.
- `templates/all records.html`: admin-only Bootstrap DataTable for every submitted report and every captured field.
- `templates/register.html`: the Computer Register officers browse, linking each officer to a prefilled report.
- `templates/assets.html`: admin-only DataTable of the full ICT Computer Register.
- `form_schema.py`: field metadata (label, type, required) driving the form, validation, and tables.
- `asset_register.py`: loads `data/ict_computer_register.csv` and searches it for the form's serial-number lookup.
- `models.py`: SQLAlchemy models for `users` (one account for the whole system), `maintenance_reports`, and `computer_assets`.
- `auth.py`: the shared sign-in, session, and capability checks.
- `admin_users.py`: the administrator console — adding accounts and assigning rights.
- `extensions.py`: the shared `db`, `migrate`, and `socketio` instances.
- `HELP_DESK/`: the ICT help desk blueprint mounted at `/helpdesk`.
- Docker and Docker Compose files for Flask plus PostgreSQL.

## Report Fields

`maintenance_reports` holds one row per submitted report:

| Group | Columns |
| --- | --- |
| Report details | `serial_no`, `computer_name`, `department`, `officer_name`, `report_time`, `report_date` |
| Services 1-7 | `peripherals_cleaned`, `data_backup_schedule_status`, `windows_firewall_status`, `allowed_firewall_exceptions`, `windows_update_status`, `unneeded_running_services`, `autoruns` |
| Services 8-14 | `unneeded_software`, `antivirus_auto_protect_status`, `last_antivirus_update`, `windows_user_accounts`, `disk_defragmentation_done`, `free_disk_space`, `other_observations` |
| Sign-off | `officer_sign_name`, `officer_signature`, `officer_sign_date`, `ict_assigned_officer_name`, `ict_assigned_officer_signature`, `ict_assigned_officer_sign_date`, `ict_manager_name`, `ict_manager_signature`, `ict_manager_sign_date` |
| Audit | `submitted_at`, `submitted_by_username`, `updated_at`, `updated_by_username` |
| Register link | `asset_id` &rarr; `computer_assets.id` |

The four identifying columns say where their value comes from, which is what the form's labels ask for:

| Column | Label on the form | Where the officer reads it |
| --- | --- | --- |
| `serial_no` | Chassis SNo (from BIOS) | The BIOS, or the register lookup |
| `computer_name` | Chassis Model (from BIOS) | The BIOS, e.g. HP ProBook G5 |
| `desktop_sno` | Desktop SNo (from the desktop) | The sticker on the desktop unit |
| `desktop_model` | Desktop Model | The desktop, e.g. HP ProDesk 400 G7 |
| `officer_name` | Officer Owning Computer | The officer the machine is assigned to |

`computer_name`, `department`, `officer_name`, and `report_date` are required. The two Yes/No
questions (`peripherals_cleaned`, `disk_defragmentation_done`) are nullable booleans, so an
unanswered question stays `NULL` rather than defaulting to "No". The list questions (firewall
exceptions, running services, autoruns, unneeded software, user accounts) are `TEXT` columns
holding one entry per line.

### Signatures

The three sign-off signatures (`officer_signature`, `ict_assigned_officer_signature`,
`ict_manager_signature`) are drawn on a signature pad — mouse, pen, or finger — and stored as a
PNG data URL in a `TEXT` column. A signature that was not drawn on the pad is rejected, an unsigned
report is still accepted, and the record pages render a stored signature as an image. The
notification email says `(signed)` rather than carrying the base64.

### Editing a submitted report

An ICT manager (`helpdesk_role = manager`, or the administrator) can correct a report after it has
been submitted at `/maintenance/<id>/edit`. The form comes back prefilled, including the signature
pads. The edit overwrites the report in place and records who did it in `updated_at` and
`updated_by_username`; the report page then shows an **Edited** badge. Everyone else gets an Edit
button they cannot see and a route they cannot reach.

## ICT Computer Register

`computer_assets` holds the organisation's ICT asset register, exported from the assets workbook
(sheet *ICT Computer Register*) into `data/ict_computer_register.csv` and loaded at seed time.

Typing the first three characters of a serial number into **Chassis SNo** searches the register and
offers a dropdown of matching machines; picking one fills in the **Chassis Model** and the
**Officer Owning Computer**. Serial prefixes rank first, and a monitor's serial or an asset tag
finds its machine too. `/admin/assets` lists the whole register.

### How a report is tied to the register

`maintenance_reports.asset_id` is a foreign key to `computer_assets.id` (`ON DELETE SET NULL`), so a
report points at the register line it was filed against instead of only copying its text. It is set
three ways, in order:

1. the hidden `asset_id` the form carries when it was opened from the register or from the
   serial-number dropdown;
2. failing that, an exact match of the report's serial number against the register, ignoring case
   and surrounding spaces;
3. failing that, `NULL` — a report can still be filed for a machine that is not on the register.

A manager's edit re-resolves the link, so correcting a serial number moves the report to the right
register line (or clears it). The migration that adds the column backfills existing reports by the
same serial-number match. Where a serial appears on more than one register line, the lowest id wins,
so the link is never ambiguous. The report page names the register entry when one is linked.

**Computer Register** in the navbar opens `/assets`: serial number, make & model, and responsible
officer for every line on the register. Clicking an officer's name opens the maintenance form with
those three values already filled in, so a report starts from the register rather than from a blank
page. Lines with no officer recorded (shared phones, spare gear) are listed after the assigned ones.

| Route | Purpose |
| --- | --- |
| `/assets` | The register — serial, model, officer; officer names open a prefilled report |
| `/maintenance?asset=<id>` | The form prefilled from one register line |
| `/assets/lookup?q=` | JSON suggestions for the dropdown; needs at least 3 characters, returns at most 12 |
| `/admin/assets` | Admin-only table of every registered asset, all columns |

To refresh the register after the workbook changes, re-export the sheet to
`data/ict_computer_register.csv` and reload the table.

## ICT Help Desk

`HELP_DESK/` is a **blueprint on this same app**, not a separate service. It is mounted at
`/helpdesk`, sharing this app's host, port, database, and migration chain — so running Flask
once from the project root serves both, and the **Report a Problem to the Help Desk** button
on the maintenance form is an ordinary internal link that works on whatever port you use.

Users submit computer complaints, the help desk sees them arrive on a live Socket.IO
dashboard, and both sides are notified the moment a problem is resolved. See
`HELP_DESK/README.md` for the routes, roles, and Socket.IO events.

Because the app now serves WebSockets, run it with `python app.py` (which calls
`socketio.run`) rather than `flask run`, and under gunicorn use the `gthread` worker with a
single process — both are already configured in `Dockerfile` and `deploy.sh`.

## Accounts

One `users` table and one sign-in at `/login` cover the whole system — the maintenance
admin area and the ICT help desk. Capability comes from the account, not from a second
login: `is_admin` opens `/admin`, and `helpdesk_role` (`officer` or `manager`) opens
`/helpdesk/staff`. Signing in lands you on the area your account is for.

**Every seeded password is `field.123`.**

| Username | Password | Admin | Help desk role | Can close tickets |
| --- | --- | :-: | --- | :-: |
| `jonyango` | `field.123` | ✓ | manager | ✓ |
| `ictmanager` | `field.123` | | manager | ✓ |
| `icthelpdesk` | `field.123` | | officer | |

New accounts get `field.123` (`DEFAULT_USER_PASSWORD`). Change these in production via
`ADMIN_PASSWORD`, `HELPDESK_*_PASSWORD`, and `DEFAULT_USER_PASSWORD`.

### Administrator console

`jonyango` manages accounts and rights from `/admin`:

| Route | Purpose |
| --- | --- |
| `/admin` | Console — account, report, and asset counts, newest accounts |
| `/admin/users` | Every account, searchable and filterable by rights |
| `/admin/users/new` | Add an account, assigning roles and privileges up front |
| `/admin/users/<id>` | Change an account's rights, name, email |
| `/admin/users/<id>/password` | Reset a password (blank = the default) |
| `/admin/users/<id>/status` | Deactivate or reactivate an account |
| `/admin/assets` | The ICT Computer Register |

Two rights are assigned independently, both at creation and afterwards:

- **Administrator** — the console, user management, every maintenance report, and closing tickets.
- **Help desk access** — `ICT intern`, `Help desk officer` or `ICT manager`, which decides how
  the account works the queue. Managers may also close tickets and take over another
  person's task.

Plus an **email this account** switch that puts the account on the notification list.

Guardrails stop the console being locked: an administrator cannot remove their own
administrator rights or deactivate their own account, and the last active administrator
cannot be demoted. Accounts are deactivated rather than deleted, because tickets reference
the person who handled them.

Reporting a problem needs no account at all — reporters get a private tracking link.

## Run With Docker

```bash
docker compose up --build
```

Open:

- Form: `http://localhost:5000/maintenance`
- Admin: `http://localhost:5000/admin`
- Admin records: `http://localhost:5000/admin/records`

The `db` service creates the PostgreSQL database from `.env`. The web container runs `flask --app 'app:create_app()' db upgrade` and then `flask --app 'app:create_app()' seed-data` before starting Gunicorn, so migrations, the `jonyango` admin, and the first two seed reports are applied automatically.

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
python app.py            # honours APP_HOST / APP_PORT, defaults to 0.0.0.0:5000
```

`python app.py` is used instead of `flask run` because `socketio.run` is what keeps
WebSocket support for the help desk.

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
- runs `seed-data` to create the admin user and first two reports.

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

## Complaints Tracker

Every signed-in account gets a **Complaints** button in the navbar, badged with the number
of complaints on the platform. It opens `/helpdesk/complaints`: a tracker of every
complaint, with status tiles, status filters, and search across reference, subject,
reporter, department, and computer name.

Any account holder can read the tracker and open a ticket. Working tickets — picking,
returning, transferring, re-prioritising and resolving — needs a help desk role
(`intern`, `officer` or `manager`), and closing stays with the reporter or an ICT manager.
See `HELP_DESK/README.md` for the work queue.

## Email Notifications

Every submitted response is emailed to **the addresses in `NOTIFY_EMAILS` plus every
platform account that has an email address**, deduplicated case-insensitively. An account
can be left off the list with the *Email this account* switch when the admin creates it
(`users.receives_notifications`).

What gets sent:

- a new help desk complaint, with the reporter set as `Reply-To` so ICT can answer directly;
- a submitted computer maintenance report, with every field.

Configure the sending account in `.env` — `MAIL_PASSWORD` must be a Gmail **App Password**,
not the account password:

```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=<sending gmail address>
MAIL_PASSWORD=<gmail app password>
MAIL_SENDER_NAME=PBORA
MAIL_DEFAULT_SENDER=<sending gmail address>
NOTIFY_EMAILS=jonyango@pbora.go.ke,ictsupport@pbora.go.ke
```

`MAIL_SENDER_NAME` is the name recipients see in their inbox. Without it Gmail falls back
to the sending account's own name, so the header is built as
`PBORA <account@gmail.com>`.

Mail is best-effort by design: it is sent on a background thread, and any failure —
bad credentials, Gmail unreachable, a broken template — is logged and swallowed. A
submission is never lost or turned into an error because email did not work. Leave
`MAIL_USERNAME` empty to disable notifications entirely.

`.env` holds live credentials and is **not** tracked by git. Use `.env.example` as the
committed template.

## Tests

Run them with the project virtualenv — the help desk needs `Flask-SocketIO`, which is in
`requirements.txt`:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest
.venv/bin/python -m pytest tests -q
```

109 tests: the maintenance form and its typed columns, the unified accounts, the complaints tracker, email notifications, plus the help desk's validation, token
access rules, close-permission matrix, reopening, SLA recalculation, audit trail, CSV export,
and Socket.IO room authorisation and broadcasts.
