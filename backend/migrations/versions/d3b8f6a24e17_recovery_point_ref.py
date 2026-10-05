"""recovery point ref

Revision ID: d3b8f6a24e17
Revises: c7a2e94d1f08
Create Date: 2026-10-05 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd3b8f6a24e17'
down_revision: Union[str, Sequence[str], None] = 'c7a2e94d1f08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: recovery points are referenced the cloud-neutral way."""
    op.alter_column('teardown_recovery_points', 'recovery_point_arn', new_column_name='recovery_point_ref')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('teardown_recovery_points', 'recovery_point_ref', new_column_name='recovery_point_arn')
