"""add composite indexes for bounded profit queries

Revision ID: 20260920_0033
Revises: 20260920_0032
"""

from alembic import op


revision = '20260920_0033'
down_revision = '20260920_0032'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_financial_store_marketplace_event_nm', 'marketplace_financial_lines',
                    ['store_id', 'marketplace', 'event_date', 'nm_id'])
    op.create_index('ix_advertising_store_marketplace_event_nm', 'marketplace_advertising_lines',
                    ['store_id', 'marketplace', 'event_date', 'nm_id'])
    op.create_index('ix_cost_version_store_marketplace_nm_effective', 'product_cost_versions',
                    ['store_id', 'marketplace', 'nm_id', 'effective_on'])


def downgrade():
    op.drop_index('ix_cost_version_store_marketplace_nm_effective', table_name='product_cost_versions')
    op.drop_index('ix_advertising_store_marketplace_event_nm', table_name='marketplace_advertising_lines')
    op.drop_index('ix_financial_store_marketplace_event_nm', table_name='marketplace_financial_lines')
