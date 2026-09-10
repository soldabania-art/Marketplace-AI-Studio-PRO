"""immutable cost import preview batches

Revision ID: 20260910_0020
Revises: 20260910_0019
"""
from alembic import op
import sqlalchemy as sa

revision = '20260910_0020'
down_revision = '20260910_0019'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cost_import_batches',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('store_id', sa.String(length=36), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('source_system', sa.String(length=32), nullable=False),
        sa.Column('source_document_reference', sa.String(length=300), nullable=False),
        sa.Column('rows', sa.JSON(), nullable=False),
        sa.Column('payload_sha256', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('committed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'payload_sha256', name='uq_cost_import_store_payload'),
    )
    for column in ('workspace_id', 'store_id', 'created_by_user_id', 'source_system', 'payload_sha256', 'status', 'expires_at', 'committed_at', 'created_at'):
        op.create_index(f'ix_cost_import_batches_{column}', 'cost_import_batches', [column])


def downgrade():
    op.drop_table('cost_import_batches')
