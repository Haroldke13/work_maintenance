"""unify staff into users

The help desk kept its own `staff` table, so ICT people held two sets of
credentials. This folds those accounts into `users` (which gains `full_name`,
`helpdesk_role` and `is_active`), remaps ticket assignments onto the surviving
user ids, and drops `staff`.

Existing staff rows are migrated, not discarded: a staff account whose username
already exists in `users` is merged onto that user; the rest are inserted.

Revision ID: c8d5a1e37b90
Revises: 91f61b2b7283
Create Date: 2026-09-03 13:05:00.000000

"""
import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = 'c8d5a1e37b90'
down_revision = '91f61b2b7283'
branch_labels = None
depends_on = None

# `tickets.assigned_to_id` was created with an unnamed FK to `staff`. SQLite cannot
# drop an unnamed constraint, so batch mode is given a convention that reproduces
# the name Alembic would have used; PostgreSQL reports the real name by reflection.
FK_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
OLD_FK = "fk_tickets_assigned_to_id_staff"
NEW_FK = "fk_tickets_assigned_to_id_users"


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('full_name', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('helpdesk_role', sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true())
        )

    bind = op.get_bind()
    staff_to_user = _migrate_staff_accounts(bind)

    # Order matters: the old constraint has to go before the column can hold user
    # ids, and the new one can only be added once every value points at a user.
    _drop_foreign_key(bind, OLD_FK, 'staff')
    _remap_ticket_assignments(bind, staff_to_user)
    _create_foreign_key(bind, NEW_FK, 'users')

    op.drop_index(op.f('ix_staff_username'), table_name='staff')
    op.drop_table('staff')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('is_active', server_default=None)


def _drop_foreign_key(bind, sqlite_name: str, referred_table: str) -> None:
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table('tickets', naming_convention=FK_CONVENTION) as batch_op:
            batch_op.drop_constraint(sqlite_name, type_='foreignkey')
        return

    for foreign_key in sa.inspect(bind).get_foreign_keys('tickets'):
        if foreign_key['referred_table'] == referred_table and foreign_key['name']:
            op.drop_constraint(foreign_key['name'], 'tickets', type_='foreignkey')


def _create_foreign_key(bind, name: str, referred_table: str) -> None:
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table('tickets', naming_convention=FK_CONVENTION) as batch_op:
            batch_op.create_foreign_key(name, referred_table, ['assigned_to_id'], ['id'])
        return

    op.create_foreign_key(name, 'tickets', referred_table, ['assigned_to_id'], ['id'])


def _migrate_staff_accounts(bind) -> dict[int, int]:
    """Fold every staff row into `users`; return {staff_id: user_id}."""
    staff_rows = bind.execute(
        sa.text(
            "SELECT id, username, full_name, password_hash, role, is_active, created_at FROM staff"
        )
    ).mappings().all()

    mapping = {}
    for row in staff_rows:
        existing = bind.execute(
            sa.text("SELECT id FROM users WHERE username = :username"),
            {"username": row["username"]},
        ).scalar()

        if existing is not None:
            bind.execute(
                sa.text(
                    "UPDATE users SET full_name = COALESCE(full_name, :full_name), "
                    "helpdesk_role = :role, is_active = :is_active WHERE id = :id"
                ),
                {
                    "full_name": row["full_name"],
                    "role": row["role"],
                    "is_active": row["is_active"],
                    "id": existing,
                },
            )
            mapping[row["id"]] = existing
            continue

        bind.execute(
            sa.text(
                "INSERT INTO users (username, full_name, password_hash, is_admin, "
                "helpdesk_role, is_active, created_by, created_at) "
                "VALUES (:username, :full_name, :password_hash, :is_admin, "
                ":role, :is_active, :created_by, :created_at)"
            ),
            {
                "username": row["username"],
                "full_name": row["full_name"],
                "password_hash": row["password_hash"],
                "is_admin": False,
                "role": row["role"],
                "is_active": row["is_active"],
                "created_by": "helpdesk-migration",
                "created_at": row["created_at"],
            },
        )
        mapping[row["id"]] = bind.execute(
            sa.text("SELECT id FROM users WHERE username = :username"),
            {"username": row["username"]},
        ).scalar()

    return mapping


def _remap_ticket_assignments(bind, staff_to_user: dict[int, int]) -> None:
    """Move `tickets.assigned_to_id` from staff ids onto user ids.

    This must be ONE statement. Staff ids and user ids share a range, so applying
    the mapping as a sequence of UPDATEs would re-hit rows a previous UPDATE had
    already rewritten (staff 2 -> user 3, then staff 3 -> user 1, and a ticket
    assigned to staff 2 ends up on user 1).
    """
    if not staff_to_user:
        bind.execute(sa.text("UPDATE tickets SET assigned_to_id = NULL"))
        return

    whens = " ".join(
        f"WHEN :staff_{staff_id} THEN :user_{staff_id}" for staff_id in staff_to_user
    )
    params = {}
    for staff_id, user_id in staff_to_user.items():
        params[f"staff_{staff_id}"] = staff_id
        params[f"user_{staff_id}"] = user_id

    # Any id with no mapping is cleared, so nothing dangles against the new key.
    bind.execute(
        sa.text(
            f"UPDATE tickets SET assigned_to_id = CASE assigned_to_id {whens} ELSE NULL END "
            "WHERE assigned_to_id IS NOT NULL"
        ),
        params,
    )


def downgrade():
    bind = op.get_bind()

    op.create_table(
        'staff',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('full_name', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_staff_username'), 'staff', ['username'], unique=True)

    bind.execute(
        sa.text(
            "INSERT INTO staff (username, full_name, password_hash, role, is_active, created_at) "
            "SELECT username, COALESCE(full_name, username), password_hash, helpdesk_role, "
            "is_active, created_at FROM users WHERE helpdesk_role IS NOT NULL"
        )
    )

    _drop_foreign_key(bind, NEW_FK, 'users')
    # Regenerated staff ids do not line up with the user ids they came from.
    bind.execute(sa.text("UPDATE tickets SET assigned_to_id = NULL"))
    _create_foreign_key(bind, OLD_FK, 'staff')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_active')
        batch_op.drop_column('helpdesk_role')
        batch_op.drop_column('full_name')
