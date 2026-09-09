"""add the ICT computer register

Holds the organisation's asset register so the maintenance form can look a
serial number up and fill in the responsible officer and the model.

Revision ID: f7c3d81a4e26
Revises: e2b6f4c07a19
Create Date: 2026-09-09 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7c3d81a4e26'
down_revision = 'e2b6f4c07a19'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'computer_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('serial_no', sa.String(length=120), nullable=True),
        sa.Column('all_serials', sa.Text(), nullable=True),
        sa.Column('tag_numbers', sa.Text(), nullable=True),
        sa.Column('asset_description', sa.String(length=200), nullable=True),
        sa.Column('make_model', sa.String(length=300), nullable=True),
        sa.Column('responsible_officer', sa.String(length=160), nullable=True),
        sa.Column('location', sa.String(length=120), nullable=True),
        sa.Column('condition', sa.String(length=60), nullable=True),
        sa.Column('notes', sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('computer_assets', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_computer_assets_serial_no'), ['serial_no'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_computer_assets_responsible_officer'),
            ['responsible_officer'],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table('computer_assets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_computer_assets_responsible_officer'))
        batch_op.drop_index(batch_op.f('ix_computer_assets_serial_no'))
    op.drop_table('computer_assets')
