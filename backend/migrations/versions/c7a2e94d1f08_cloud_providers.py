"""cloud providers

Revision ID: c7a2e94d1f08
Revises: b5f0d3a91c27
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7a2e94d1f08'
down_revision: Union[str, Sequence[str], None] = 'b5f0d3a91c27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROVIDER_TABLES = ('projects', 'networks', 'landing_zone_designs', 'teardowns', 'account_bindings')
WIDENED = (('account_bindings', 'account_id'), ('networks', 'account_id'), ('teardowns', 'backup_account_id'),
           ('teardown_environments', 'account_id'), ('teardown_recovery_points', 'account_id'))


def _provider() -> sa.Column:
    return sa.Column('provider', sa.String(length=16), nullable=False, server_default='aws')


def upgrade() -> None:
    """Upgrade schema: every cloud-specific row names its provider (existing rows are AWS); ids fit any cloud."""
    for table in PROVIDER_TABLES:
        op.add_column(table, _provider())
    op.add_column('regions', _provider())
    op.drop_constraint('regions_pkey', 'regions', type_='primary')
    op.create_primary_key('regions_pkey', 'regions', ['provider', 'id'])
    for table, column in WIDENED:
        op.alter_column(table, column, type_=sa.String(length=64), existing_type=sa.String(length=12))
    op.drop_constraint('account_bindings_account_id_key', 'account_bindings', type_='unique')
    op.drop_constraint('account_bindings_environment_id_portfolio_id_key', 'account_bindings', type_='unique')
    op.create_unique_constraint('account_bindings_provider_account_id_key', 'account_bindings',
                                ['provider', 'account_id'])
    op.create_unique_constraint('account_bindings_environment_id_portfolio_id_provider_key', 'account_bindings',
                                ['environment_id', 'portfolio_id', 'provider'])


def downgrade() -> None:
    """Downgrade schema (only possible while every row is AWS)."""
    op.drop_constraint('account_bindings_environment_id_portfolio_id_provider_key', 'account_bindings', type_='unique')
    op.drop_constraint('account_bindings_provider_account_id_key', 'account_bindings', type_='unique')
    op.create_unique_constraint('account_bindings_environment_id_portfolio_id_key', 'account_bindings',
                                ['environment_id', 'portfolio_id'])
    op.create_unique_constraint('account_bindings_account_id_key', 'account_bindings', ['account_id'])
    for table, column in WIDENED:
        op.alter_column(table, column, type_=sa.String(length=12), existing_type=sa.String(length=64))
    op.drop_constraint('regions_pkey', 'regions', type_='primary')
    op.create_primary_key('regions_pkey', 'regions', ['id'])
    op.drop_column('regions', 'provider')
    for table in PROVIDER_TABLES:
        op.drop_column(table, 'provider')
