"""project changes

Revision ID: 8c41e5d2b7a9
Revises: 3b7d2f9c1a60
Create Date: 2026-10-04 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '8c41e5d2b7a9'
down_revision: Union[str, Sequence[str], None] = '3b7d2f9c1a60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projects', sa.Column('revision', sa.Integer(), nullable=False, server_default='1'))
    op.create_table(
        'project_changes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('project_name', sa.String(length=64), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('request', JSON, nullable=False),
        sa.Column('summary', JSON, nullable=False),
        sa.Column('base_commit', sa.String(length=64), nullable=False),
        sa.Column('branch', sa.String(length=128), nullable=False),
        sa.Column('state', sa.String(length=16), nullable=False),
        sa.Column('pull_request_number', sa.Integer(), nullable=True),
        sa.Column('pull_request_url', sa.String(length=512), nullable=True),
        sa.Column('merge_commit', sa.String(length=64), nullable=True),
        sa.Column('created_by', sa.String(length=128), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_name'], ['projects.name']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_project_changes_project_name'), 'project_changes', ['project_name'], unique=False)
    op.add_column('jobs', sa.Column('kind', sa.String(length=16), nullable=False, server_default='provision'))
    op.add_column('jobs', sa.Column('change_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_jobs_change_id', 'jobs', 'project_changes', ['change_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_jobs_change_id', 'jobs', type_='foreignkey')
    op.drop_column('jobs', 'change_id')
    op.drop_column('jobs', 'kind')
    op.drop_index(op.f('ix_project_changes_project_name'), table_name='project_changes')
    op.drop_table('project_changes')
    op.drop_column('projects', 'revision')
