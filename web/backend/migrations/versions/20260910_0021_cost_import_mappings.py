"""store-scoped cost import mapping presets

Revision ID: 20260910_0021
Revises: 20260910_0020
"""
from alembic import op
import sqlalchemy as sa

revision = '20260910_0021'
down_revision = '20260910_0020'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cost_import_mappings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('store_id', sa.String(length=36), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('source_system', sa.String(length=32), nullable=False),
        sa.Column('mapping', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'name', name='uq_cost_import_mapping_store_name'),
    )
    for column in ('workspace_id', 'store_id', 'created_by_user_id', 'source_system', 'created_at', 'updated_at'):
        op.create_index(f'ix_cost_import_mappings_{column}', 'cost_import_mappings', [column])


def downgrade():
    op.drop_table('cost_import_mappings')
