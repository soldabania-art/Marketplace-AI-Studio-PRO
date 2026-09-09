"""director approval inbox and emergency control

Revision ID: 20260909_0013
Revises: 20260909_0012
"""
from alembic import op
import sqlalchemy as sa

revision = '20260909_0013'
down_revision = '20260909_0012'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('director_runs',
        sa.Column('id',sa.String(36),primary_key=True), sa.Column('workspace_id',sa.String(36),nullable=False),
        sa.Column('store_id',sa.String(36),nullable=False), sa.Column('marketplace',sa.String(32),nullable=False),
        sa.Column('fingerprint',sa.String(64),nullable=False), sa.Column('source_payload',sa.JSON(),nullable=False),
        sa.Column('summary_payload',sa.JSON(),nullable=False), sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'],['stores.id'],ondelete='CASCADE'),
        sa.UniqueConstraint('store_id','fingerprint',name='uq_director_run_store_fingerprint'))
    op.create_table('director_actions',
        sa.Column('id',sa.String(36),primary_key=True), sa.Column('run_id',sa.String(36),nullable=False),
        sa.Column('workspace_id',sa.String(36),nullable=False), sa.Column('store_id',sa.String(36),nullable=False),
        sa.Column('action_key',sa.String(200),nullable=False), sa.Column('kind',sa.String(40),nullable=False),
        sa.Column('status',sa.String(40),nullable=False), sa.Column('requires_approval',sa.Boolean(),nullable=False),
        sa.Column('recommendation_payload',sa.JSON(),nullable=False), sa.Column('decision_note',sa.String(1000),nullable=False),
        sa.Column('decided_by_user_id',sa.String(36),nullable=True), sa.Column('decided_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('result_payload',sa.JSON(),nullable=False), sa.Column('rollback_payload',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['run_id'],['director_runs.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'],['stores.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['decided_by_user_id'],['users.id'],ondelete='RESTRICT'),
        sa.UniqueConstraint('run_id','action_key',name='uq_director_action_run_key'))
    op.create_table('automation_controls',
        sa.Column('id',sa.String(36),primary_key=True), sa.Column('workspace_id',sa.String(36),nullable=False),
        sa.Column('store_id',sa.String(36),nullable=False), sa.Column('marketplace',sa.String(32),nullable=False),
        sa.Column('stopped',sa.Boolean(),nullable=False), sa.Column('reason',sa.String(1000),nullable=False),
        sa.Column('changed_by_user_id',sa.String(36),nullable=False), sa.Column('changed_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'],['stores.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by_user_id'],['users.id'],ondelete='RESTRICT'),
        sa.UniqueConstraint('store_id','marketplace',name='uq_automation_control_store_marketplace'))
    op.create_table('operational_audit_events',
        sa.Column('id',sa.String(36),primary_key=True), sa.Column('workspace_id',sa.String(36),nullable=False),
        sa.Column('store_id',sa.String(36),nullable=False), sa.Column('user_id',sa.String(36),nullable=False),
        sa.Column('event_type',sa.String(80),nullable=False), sa.Column('entity_type',sa.String(40),nullable=False),
        sa.Column('entity_id',sa.String(80),nullable=False), sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['store_id'],['stores.id'],ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'],['users.id'],ondelete='RESTRICT'))
    for table, columns in {
        'director_runs':['workspace_id','store_id','marketplace','fingerprint','created_at'],
        'director_actions':['run_id','workspace_id','store_id','action_key','kind','status','requires_approval','decided_by_user_id','decided_at','created_at','updated_at'],
        'automation_controls':['workspace_id','store_id','marketplace','stopped','changed_by_user_id','changed_at'],
        'operational_audit_events':['workspace_id','store_id','user_id','event_type','entity_type','entity_id','created_at'],
    }.items():
        for column in columns: op.create_index(f'ix_{table}_{column}',table,[column])


def downgrade():
    op.drop_table('operational_audit_events')
    op.drop_table('automation_controls')
    op.drop_table('director_actions')
    op.drop_table('director_runs')
