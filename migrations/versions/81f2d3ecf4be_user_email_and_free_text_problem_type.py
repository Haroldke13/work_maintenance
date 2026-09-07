"""user email and free-text problem type

Accounts gain an email address (the jonyango account pegs to jonyango@pbora.go.ke),
and "Describe the problem type" became a textarea, so `tickets.other_category`
widens from VARCHAR(160) to TEXT.

Revision ID: 81f2d3ecf4be
Revises: c8d5a1e37b90
Create Date: 2026-09-03 14:10:16.217249

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '81f2d3ecf4be'
down_revision = 'c8d5a1e37b90'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.alter_column('other_category',
               existing_type=sa.VARCHAR(length=160),
               type_=sa.Text(),
               existing_nullable=True)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=160), nullable=True))



def downgrade():
    # Narrowing TEXT back to VARCHAR(160) is lossy: any problem-type description
    # longer than 160 characters will fail (PostgreSQL) or be kept (SQLite).
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email')

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.alter_column('other_category',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=160),
               existing_nullable=True)

