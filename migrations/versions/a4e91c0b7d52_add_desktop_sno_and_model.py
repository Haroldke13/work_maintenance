"""add desktop serial number and model to maintenance reports

Both columns are optional so existing reports stay valid.

Revision ID: a4e91c0b7d52
Revises: 99ddc6c3a0ba
Create Date: 2026-09-08 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4e91c0b7d52'
down_revision = '99ddc6c3a0ba'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('maintenance_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('desktop_sno', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('desktop_model', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('maintenance_reports', schema=None) as batch_op:
        batch_op.drop_column('desktop_model')
        batch_op.drop_column('desktop_sno')
