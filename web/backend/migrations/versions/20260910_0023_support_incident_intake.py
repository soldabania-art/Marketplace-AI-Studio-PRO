"""safe support incident intake

Revision ID: 20260910_0023
Revises: 20260910_0022
"""
from alembic import op
import sqlalchemy as sa

revision = '20260910_0023'
down_revision = '20260910_0022'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('support_tickets',
        sa.Column('id', sa.String(length=36), nullable=False), sa.Column('workspace_id', sa.String(length=36), nullable=False),
        sa.Column('store_id', sa.String(length=36), nullable=False), sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False), sa.Column('severity', sa.String(length=16), nullable=False),
        sa.Column('forced_escalation_reason', sa.String(length=80), nullable=False), sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('sanitized_description', sa.Text(), nullable=False), sa.Column('correlation_id', sa.String(length=120), nullable=False),
        sa.Column('request_sha256', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'), sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('store_id', 'created_by_user_id', 'request_sha256', name='uq_support_ticket_actor_request'))
    for column in ('workspace_id','store_id','created_by_user_id','category','severity','forced_escalation_reason','status','correlation_id','request_sha256','created_at','updated_at'):
        op.create_index(f'ix_support_tickets_{column}', 'support_tickets', [column])
    op.create_table('incident_evidence_bundles',
        sa.Column('id', sa.String(length=36), nullable=False), sa.Column('ticket_id', sa.String(length=36), nullable=False),
        sa.Column('workspace_id', sa.String(length=36), nullable=False), sa.Column('store_id', sa.String(length=36), nullable=False),
        sa.Column('bundle_sha256', sa.String(length=64), nullable=False), sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['ticket_id'], ['support_tickets.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'], ['stores.id'], ondelete='CASCADE'), sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticket_id', name='uq_incident_evidence_ticket'))
    for column in ('ticket_id','workspace_id','store_id','bundle_sha256','created_at'):
        op.create_index(f'ix_incident_evidence_bundles_{column}', 'incident_evidence_bundles', [column])

def downgrade():
    op.drop_table('incident_evidence_bundles'); op.drop_table('support_tickets')
