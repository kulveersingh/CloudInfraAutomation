"""network refs

Revision ID: e9c4a17b52d6
Revises: d3b8f6a24e17
Create Date: 2026-10-05 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e9c4a17b52d6'
down_revision: Union[str, Sequence[str], None] = 'd3b8f6a24e17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RENAMES = (('vpc_id', 'network_ref'), ('private_subnet_ids', 'subnet_refs'), ('security_group_ids', 'firewall_refs'))


def upgrade() -> None:
    """Upgrade schema: an organization network is described the cloud-neutral way (§22.4)."""
    for old, new in RENAMES:
        op.alter_column('networks', old, new_column_name=new)
    op.alter_column('networks', 'network_ref', type_=sa.String(length=255), existing_type=sa.String(length=32))


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('networks', 'network_ref', type_=sa.String(length=32), existing_type=sa.String(length=255))
    for old, new in RENAMES:
        op.alter_column('networks', new, new_column_name=old)
