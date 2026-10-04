"""project commit sha

Revision ID: 3b7d2f9c1a60
Revises: ec23e008f808
Create Date: 2026-10-04 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3b7d2f9c1a60'
down_revision: Union[str, Sequence[str], None] = 'ec23e008f808'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projects', sa.Column('commit_sha', sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'commit_sha')
