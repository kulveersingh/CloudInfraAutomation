"""landing zone per provider

Revision ID: a7d3c5e19b42
Revises: e9c4a17b52d6
Create Date: 2026-10-06 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7d3c5e19b42'
down_revision: Union[str, Sequence[str], None] = 'e9c4a17b52d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: each cloud has its own landing zone, numbered from v1 (§22.10)."""
    op.drop_constraint('landing_zone_designs_version_key', 'landing_zone_designs', type_='unique')
    op.create_unique_constraint('landing_zone_designs_provider_version_key', 'landing_zone_designs',
                                ['provider', 'version'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('landing_zone_designs_provider_version_key', 'landing_zone_designs', type_='unique')
    op.create_unique_constraint('landing_zone_designs_version_key', 'landing_zone_designs', ['version'])
