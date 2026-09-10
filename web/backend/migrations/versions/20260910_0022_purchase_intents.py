"""server-owned public purchase intents

Revision ID: 20260910_0022
Revises: 20260910_0021
"""
from alembic import op
import sqlalchemy as sa

revision = '20260910_0022'
down_revision = '20260910_0021'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'purchase_intents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('requested_plan', sa.String(length=24), nullable=False),
        sa.Column('active_channel', sa.String(length=32), nullable=False),
        sa.Column('marketplace_interest', sa.String(length=32), nullable=True),
        sa.Column('requested_stores', sa.Integer(), nullable=False),
        sa.Column('requested_modules', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('fulfilled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', name='uq_purchase_intent_workspace'),
    )
    for column in ('workspace_id', 'created_by_user_id', 'requested_plan', 'active_channel', 'marketplace_interest', 'status', 'created_at'):
        op.create_index(f'ix_purchase_intents_{column}', 'purchase_intents', [column])


def downgrade():
    op.drop_table('purchase_intents')
