"""landing zone design edits

Revision ID: ec23e008f808
Revises: 148de0163524
Create Date: 2026-10-04 09:59:33.282216

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ec23e008f808'
down_revision: Union[str, Sequence[str], None] = '148de0163524'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('landing_zone_designs', sa.Column(
        'edits', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
        nullable=False, server_default='[]'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('landing_zone_designs', 'edits')
