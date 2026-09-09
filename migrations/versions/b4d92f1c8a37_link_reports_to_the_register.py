"""link maintenance reports to the computer register

A report records the serial number, model, and officer as free text. This adds
the foreign key that ties it to the register line those values came from, and
backfills existing reports by matching their serial number.

Revision ID: b4d92f1c8a37
Revises: f7c3d81a4e26
Create Date: 2026-09-09 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4d92f1c8a37'
down_revision = 'f7c3d81a4e26'
branch_labels = None
depends_on = None


# A serial can appear on more than one register line, so a report is tied to the
# first one recorded — the lowest id — and never to an ambiguous set.
BACKFILL = sa.text("""
    UPDATE maintenance_reports AS r
       SET asset_id = (
           SELECT MIN(a.id) FROM computer_assets AS a
            WHERE a.serial_no IS NOT NULL
              AND a.serial_no <> ''
              AND UPPER(TRIM(a.serial_no)) = UPPER(TRIM(r.serial_no))
       )
     WHERE r.serial_no IS NOT NULL AND r.serial_no <> ''
""")


def upgrade():
    with op.batch_alter_table('maintenance_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('asset_id', sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f('ix_maintenance_reports_asset_id'), ['asset_id'], unique=False
        )
        batch_op.create_foreign_key(
            'fk_maintenance_reports_asset_id_computer_assets',
            'computer_assets',
            ['asset_id'],
            ['id'],
            ondelete='SET NULL',
        )

    op.execute(BACKFILL)


def downgrade():
    with op.batch_alter_table('maintenance_reports', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_maintenance_reports_asset_id_computer_assets', type_='foreignkey'
        )
        batch_op.drop_index(batch_op.f('ix_maintenance_reports_asset_id'))
        batch_op.drop_column('asset_id')
