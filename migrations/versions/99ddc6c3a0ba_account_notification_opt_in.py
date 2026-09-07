"""account notification opt-in

Accounts on the platform are notification recipients in their own right, so the
column defaults to true for every existing row.

Revision ID: 99ddc6c3a0ba
Revises: 81f2d3ecf4be
Create Date: 2026-09-03 14:26:37.800102

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '99ddc6c3a0ba'
down_revision = '81f2d3ecf4be'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'receives_notifications',
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )



    # The default was only needed to backfill existing rows.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('receives_notifications', server_default=None)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('receives_notifications')

