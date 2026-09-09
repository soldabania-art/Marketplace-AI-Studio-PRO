"""subscription entitlement lifecycle

Revision ID: 20260909_0012
Revises: 20260909_0011
"""
from alembic import op
import sqlalchemy as sa

revision = '20260909_0012'
down_revision = '20260909_0011'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('subscriptions', sa.Column('current_period_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('current_period_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('subscriptions', sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('subscriptions', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index('ix_subscriptions_current_period_expires_at', 'subscriptions', ['current_period_expires_at'])
    op.create_table(
        'billing_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('subscription_id', sa.String(length=36), nullable=False),
        sa.Column('provider', sa.String(length=40), nullable=False),
        sa.Column('external_event_id', sa.String(length=200), nullable=False),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('payload_sha256', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'external_event_id', name='uq_billing_event_provider_external'),
    )
    op.create_index('ix_billing_events_workspace_id', 'billing_events', ['workspace_id'])
    op.create_index('ix_billing_events_subscription_id', 'billing_events', ['subscription_id'])
    op.create_index('ix_billing_events_provider', 'billing_events', ['provider'])
    op.create_index('ix_billing_events_event_type', 'billing_events', ['event_type'])
    op.create_index('ix_billing_events_payload_sha256', 'billing_events', ['payload_sha256'])
    op.create_index('ix_billing_events_processed_at', 'billing_events', ['processed_at'])


def downgrade():
    op.drop_table('billing_events')
    op.drop_index('ix_subscriptions_current_period_expires_at', table_name='subscriptions')
    op.drop_column('subscriptions', 'updated_at')
    op.drop_column('subscriptions', 'canceled_at')
    op.drop_column('subscriptions', 'cancel_at_period_end')
    op.drop_column('subscriptions', 'current_period_expires_at')
    op.drop_column('subscriptions', 'current_period_started_at')
