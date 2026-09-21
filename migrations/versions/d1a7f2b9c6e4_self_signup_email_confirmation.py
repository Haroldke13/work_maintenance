"""self-signup email confirmation

Two facts about an account, both new:

* `self_registered` — it came from the public signup form, so nobody vouched
  for its address and it must confirm before signing in. Every account that
  already exists was created by staff, which is what the False default records.
* `email_confirmed_at` — when a self-registered address was proved. Null for
  staff-created accounts, which never need to prove one.

Revision ID: d1a7f2b9c6e4
Revises: b4d92f1c8a37
Create Date: 2026-09-21 09:12:44.118920

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1a7f2b9c6e4'
down_revision = 'b4d92f1c8a37'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'self_registered',
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column('email_confirmed_at', sa.DateTime(timezone=True), nullable=True)
        )

    # The default was only needed to backfill existing rows; the model supplies
    # it for new ones.
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('self_registered', server_default=None)


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email_confirmed_at')
        batch_op.drop_column('self_registered')
