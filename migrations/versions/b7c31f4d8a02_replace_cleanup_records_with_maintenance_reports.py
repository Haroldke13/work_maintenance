"""replace cleanup_records with maintenance_reports

Swaps the JSON-blob cleanup practical table for the NGOB/ICT/104b computer
maintenance report table, where every question on the form is its own column.

Revision ID: b7c31f4d8a02
Revises: 91500de29217
Create Date: 2026-09-03 12:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c31f4d8a02'
down_revision = '91500de29217'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'maintenance_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('serial_no', sa.String(length=50), nullable=True),
        sa.Column('computer_name', sa.String(length=120), nullable=False),
        sa.Column('department', sa.String(length=120), nullable=False),
        sa.Column('officer_name', sa.String(length=120), nullable=False),
        sa.Column('report_time', sa.Time(), nullable=True),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('peripherals_cleaned', sa.Boolean(), nullable=True),
        sa.Column('data_backup_schedule_status', sa.Text(), nullable=True),
        sa.Column('windows_firewall_status', sa.Text(), nullable=True),
        sa.Column('allowed_firewall_exceptions', sa.Text(), nullable=True),
        sa.Column('windows_update_status', sa.Text(), nullable=True),
        sa.Column('unneeded_running_services', sa.Text(), nullable=True),
        sa.Column('autoruns', sa.Text(), nullable=True),
        sa.Column('unneeded_software', sa.Text(), nullable=True),
        sa.Column('antivirus_auto_protect_status', sa.Text(), nullable=True),
        sa.Column('last_antivirus_update', sa.Date(), nullable=True),
        sa.Column('windows_user_accounts', sa.Text(), nullable=True),
        sa.Column('disk_defragmentation_done', sa.Boolean(), nullable=True),
        sa.Column('free_disk_space', sa.String(length=60), nullable=True),
        sa.Column('other_observations', sa.Text(), nullable=True),
        sa.Column('officer_sign_name', sa.String(length=120), nullable=True),
        sa.Column('officer_signature', sa.String(length=120), nullable=True),
        sa.Column('officer_sign_date', sa.Date(), nullable=True),
        sa.Column('ict_assigned_officer_name', sa.String(length=120), nullable=True),
        sa.Column('ict_assigned_officer_signature', sa.String(length=120), nullable=True),
        sa.Column('ict_assigned_officer_sign_date', sa.Date(), nullable=True),
        sa.Column('ict_manager_name', sa.String(length=120), nullable=True),
        sa.Column('ict_manager_signature', sa.String(length=120), nullable=True),
        sa.Column('ict_manager_sign_date', sa.Date(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('submitted_by_username', sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('maintenance_reports', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_maintenance_reports_report_date'), ['report_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_maintenance_reports_submitted_at'), ['submitted_at'], unique=False)

    with op.batch_alter_table('cleanup_records', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cleanup_records_submitted_at'))

    op.drop_table('cleanup_records')


def downgrade():
    op.create_table(
        'cleanup_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('form_data', sa.JSON(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('submitted_by_username', sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('cleanup_records', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cleanup_records_submitted_at'), ['submitted_at'], unique=False)

    with op.batch_alter_table('maintenance_reports', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_maintenance_reports_submitted_at'))
        batch_op.drop_index(batch_op.f('ix_maintenance_reports_report_date'))

    op.drop_table('maintenance_reports')
