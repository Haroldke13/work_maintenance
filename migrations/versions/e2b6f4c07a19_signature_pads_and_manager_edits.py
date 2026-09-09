"""widen the signature columns for signature pads and record manager edits

The three sign-off signatures are now drawn on a signature pad and stored as a
PNG data URL, which does not fit in a String(120). The two audit columns record
which ICT manager last edited a submitted report, and when.

Revision ID: e2b6f4c07a19
Revises: a4e91c0b7d52
Create Date: 2026-09-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2b6f4c07a19'
down_revision = 'a4e91c0b7d52'
branch_labels = None
depends_on = None


SIGNATURE_COLUMNS = (
    'officer_signature',
    'ict_assigned_officer_signature',
    'ict_manager_signature',
)


def upgrade():
    with op.batch_alter_table('maintenance_reports', schema=None) as batch_op:
        for column in SIGNATURE_COLUMNS:
            batch_op.alter_column(
                column,
                existing_type=sa.String(length=120),
                type_=sa.Text(),
                existing_nullable=True,
            )
        batch_op.add_column(
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column('updated_by_username', sa.String(length=80), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('maintenance_reports', schema=None) as batch_op:
        batch_op.drop_column('updated_by_username')
        batch_op.drop_column('updated_at')
        for column in SIGNATURE_COLUMNS:
            batch_op.alter_column(
                column,
                existing_type=sa.Text(),
                type_=sa.String(length=120),
                existing_nullable=True,
            )
