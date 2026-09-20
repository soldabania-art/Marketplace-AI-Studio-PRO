"""add immutable effective-dated product cost versions

Revision ID: 20260920_0032
Revises: 20260914_0031_backend_heads
"""

from alembic import op
import sqlalchemy as sa


revision = '20260920_0032'
down_revision = '20260914_0031_backend_heads'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'product_cost_versions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('store_id', sa.String(length=36), sa.ForeignKey('stores.id', ondelete='CASCADE'), nullable=False),
        sa.Column('marketplace', sa.String(length=32), nullable=False, server_default='wildberries'),
        sa.Column('nm_id', sa.Integer(), nullable=False),
        sa.Column('effective_on', sa.Date(), nullable=False),
        sa.Column('cogs_kopecks', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='RUB'),
        sa.Column('operating_model', sa.String(length=32), nullable=False, server_default='legacy_total'),
        sa.Column('components', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('source_references', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('calculation_sha256', sa.String(length=64), nullable=False, server_default=''),
        sa.Column('confirmed_by_user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('source', sa.String(length=40), nullable=False),
        sa.Column('validity', sa.String(length=24), nullable=False, server_default='confirmed'),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('cogs_kopecks >= 0', name='ck_product_cost_version_nonnegative'),
        sa.CheckConstraint("currency = 'RUB'", name='ck_product_cost_version_rub'),
        sa.CheckConstraint("validity IN ('confirmed', 'unknown')", name='ck_product_cost_version_validity'),
        sa.UniqueConstraint('store_id', 'marketplace', 'nm_id', 'effective_on', name='uq_product_cost_version_effective'),
    )
    op.execute(sa.text("""
        INSERT INTO product_cost_versions (
            id, store_id, marketplace, nm_id, effective_on, cogs_kopecks, currency,
            operating_model, components, source_references, calculation_sha256,
            confirmed_by_user_id, source, validity, confirmed_at, created_at
        )
        SELECT id, store_id, marketplace, nm_id, '1970-01-01', cogs_kopecks, 'RUB',
            operating_model, components, source_references, calculation_sha256,
            confirmed_by_user_id, 'legacy_profile_backfill', 'unknown', confirmed_at, created_at
        FROM product_cost_profiles
    """))


def downgrade():
    op.drop_table('product_cost_versions')
