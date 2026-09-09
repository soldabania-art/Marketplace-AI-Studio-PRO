"""secure agent registry learning candidates

Revision ID: 20260909_0014
Revises: 20260909_0013
"""
from alembic import op
import sqlalchemy as sa

revision = '20260909_0014'
down_revision = '20260909_0013'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('agent_learning_records',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('workspace_id',sa.String(36),nullable=False),
        sa.Column('store_id',sa.String(36),nullable=False),
        sa.Column('user_id',sa.String(36),nullable=False),
        sa.Column('agent_key',sa.String(40),nullable=False),
        sa.Column('signal',sa.String(32),nullable=False),
        sa.Column('source_type',sa.String(40),nullable=False),
        sa.Column('source_id',sa.String(160),nullable=False,server_default=''),
        sa.Column('payload_sha256',sa.String(64),nullable=False),
        sa.Column('sanitized_note',sa.String(1000),nullable=False,server_default=''),
        sa.Column('status',sa.String(24),nullable=False,server_default='candidate'),
        sa.Column('reviewed_by_user_id',sa.String(36),nullable=True),
        sa.Column('review_note',sa.String(1000),nullable=False,server_default=''),
        sa.Column('reviewed_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'],['stores.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'],['users.id'],ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['reviewed_by_user_id'],['users.id'],ondelete='RESTRICT'),
        sa.UniqueConstraint('store_id','user_id','payload_sha256',name='uq_agent_learning_actor_payload'))
    for column in ('workspace_id','store_id','user_id','agent_key','signal','source_type','source_id','payload_sha256','status','reviewed_by_user_id','reviewed_at','created_at'):
        op.create_index(f'ix_agent_learning_records_{column}','agent_learning_records',[column])
    op.create_table('agent_work_orders',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('workspace_id',sa.String(36),nullable=False),
        sa.Column('store_id',sa.String(36),nullable=False),
        sa.Column('requested_by_user_id',sa.String(36),nullable=False),
        sa.Column('goal_type',sa.String(40),nullable=False),
        sa.Column('assigned_agent_key',sa.String(40),nullable=False),
        sa.Column('capability',sa.String(80),nullable=False),
        sa.Column('subject_id',sa.String(160),nullable=False,server_default=''),
        sa.Column('sanitized_instruction',sa.String(1000),nullable=False,server_default=''),
        sa.Column('request_sha256',sa.String(64),nullable=False),
        sa.Column('status',sa.String(24),nullable=False,server_default='planned'),
        sa.Column('policy_version',sa.Integer(),nullable=False),
        sa.Column('policy_sha256',sa.String(64),nullable=False),
        sa.Column('external_write',sa.Boolean(),nullable=False,server_default=sa.false()),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'],['stores.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by_user_id'],['users.id'],ondelete='RESTRICT'),
        sa.UniqueConstraint('store_id','requested_by_user_id','request_sha256',name='uq_agent_work_order_actor_request'))
    for column in ('workspace_id','store_id','requested_by_user_id','goal_type','assigned_agent_key','capability','subject_id','request_sha256','status','created_at'):
        op.create_index(f'ix_agent_work_orders_{column}','agent_work_orders',[column])


def downgrade():
    op.drop_table('agent_work_orders')
    op.drop_table('agent_learning_records')
