"""verified per-SKU cost breakdown

Revision ID: 20260910_0019
Revises: 20260910_0018
"""
from alembic import op
import sqlalchemy as sa

revision = '20260910_0019'
down_revision = '20260910_0018'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('product_cost_profiles', sa.Column('operating_model', sa.String(length=32), nullable=False, server_default='legacy_total'))
    op.add_column('product_cost_profiles', sa.Column('components', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('product_cost_profiles', sa.Column('source_references', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('product_cost_profiles', sa.Column('calculation_sha256', sa.String(length=64), nullable=False, server_default=''))
    op.create_index('ix_product_cost_profiles_operating_model', 'product_cost_profiles', ['operating_model'])
    op.create_index('ix_product_cost_profiles_calculation_sha256', 'product_cost_profiles', ['calculation_sha256'])


def downgrade():
    op.drop_index('ix_product_cost_profiles_calculation_sha256', table_name='product_cost_profiles')
    op.drop_index('ix_product_cost_profiles_operating_model', table_name='product_cost_profiles')
    op.drop_column('product_cost_profiles', 'calculation_sha256')
    op.drop_column('product_cost_profiles', 'source_references')
    op.drop_column('product_cost_profiles', 'components')
    op.drop_column('product_cost_profiles', 'operating_model')
