"""business operating profile

Revision ID: 20260910_0018
Revises: 20260910_0017
"""
from alembic import op
import sqlalchemy as sa

revision = '20260910_0018'
down_revision = '20260910_0017'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'business_operating_profiles',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('store_id', sa.String(length=36), nullable=False),
        sa.Column('marketplace', sa.String(length=32), nullable=False),
        sa.Column('operating_model', sa.String(length=32), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('confirmed_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('confirmed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['confirmed_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'marketplace', name='uq_business_profile_store_marketplace'),
    )
    for column in ('workspace_id', 'store_id', 'marketplace', 'operating_model', 'status', 'confirmed_by_user_id', 'confirmed_at', 'created_at', 'updated_at'):
        op.create_index(f'ix_business_operating_profiles_{column}', 'business_operating_profiles', [column])


def downgrade():
    op.drop_table('business_operating_profiles')
