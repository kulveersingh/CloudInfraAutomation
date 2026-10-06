"""recovery point vault length

Revision ID: b5e2d8f41c93
Revises: a7d3c5e19b42
Create Date: 2026-10-06 17:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b5e2d8f41c93'
down_revision: Union[str, Sequence[str], None] = 'a7d3c5e19b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: an Azure vault is a full resource id, longer than 128 characters."""
    op.alter_column('teardown_recovery_points', 'vault', type_=sa.String(512), existing_type=sa.String(128))


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('teardown_recovery_points', 'vault', type_=sa.String(128), existing_type=sa.String(512))
