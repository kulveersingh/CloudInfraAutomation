"""teardowns

Revision ID: b5f0d3a91c27
Revises: 8c41e5d2b7a9
Create Date: 2026-10-05 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b5f0d3a91c27'
down_revision: Union[str, Sequence[str], None] = '8c41e5d2b7a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'teardowns',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_name', sa.String(length=64), nullable=False),
        sa.Column('scope', sa.String(length=16), nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('requested_by', sa.String(length=128), nullable=False),
        sa.Column('base_revision', sa.Integer(), nullable=False),
        sa.Column('base_request', JSON, nullable=False),
        sa.Column('base_commit', sa.String(length=64), nullable=True),
        sa.Column('backup_account_id', sa.String(length=12), nullable=False),
        sa.Column('restore_state', sa.String(length=16), nullable=True),
        sa.Column('restore_requested_by', sa.String(length=128), nullable=True),
        sa.Column('restore_decided_by', sa.String(length=128), nullable=True),
        sa.Column('restore_job_id', sa.Uuid(), nullable=True),
        sa.Column('restore_steps', JSON, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_name'], ['projects.name']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_teardowns_project_name'), 'teardowns', ['project_name'], unique=False)
    op.create_table(
        'teardown_environments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('teardown_id', sa.Uuid(), nullable=False),
        sa.Column('environment', sa.String(length=16), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('approver_role', sa.String(length=32), nullable=False),
        sa.Column('account_id', sa.String(length=12), nullable=False),
        sa.Column('regions', JSON, nullable=False),
        sa.Column('state', sa.String(length=32), nullable=False),
        sa.Column('decided_by', sa.String(length=128), nullable=True),
        sa.Column('decision_comment', sa.Text(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('revision', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('job_id', sa.Uuid(), nullable=True),
        sa.Column('completed_steps', JSON, nullable=False),
        sa.ForeignKeyConstraint(['teardown_id'], ['teardowns.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_teardown_environments_teardown_id'), 'teardown_environments', ['teardown_id'],
                    unique=False)
    op.create_table(
        'teardown_recovery_points',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('teardown_environment_id', sa.Uuid(), nullable=False),
        sa.Column('service_id', sa.String(length=64), nullable=False),
        sa.Column('logical_id', sa.String(length=255), nullable=False),
        sa.Column('resource_type', sa.String(length=128), nullable=False),
        sa.Column('physical_name', sa.String(length=255), nullable=False),
        sa.Column('region', sa.String(length=32), nullable=False),
        sa.Column('account_id', sa.String(length=12), nullable=False),
        sa.Column('recovery_point_arn', sa.String(length=512), nullable=False),
        sa.Column('vault', sa.String(length=128), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=False),
        sa.Column('locked_until', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['teardown_environment_id'], ['teardown_environments.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_teardown_recovery_points_teardown_environment_id'), 'teardown_recovery_points',
                    ['teardown_environment_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_teardown_recovery_points_teardown_environment_id'), table_name='teardown_recovery_points')
    op.drop_table('teardown_recovery_points')
    op.drop_index(op.f('ix_teardown_environments_teardown_id'), table_name='teardown_environments')
    op.drop_table('teardown_environments')
    op.drop_index(op.f('ix_teardowns_project_name'), table_name='teardowns')
    op.drop_table('teardowns')
