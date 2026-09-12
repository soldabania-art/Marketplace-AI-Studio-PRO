"""add durable background jobs

Revision ID: 20260907_0002
Revises: 20260907_0001
"""
from alembic import op
import sqlalchemy as sa

revision='20260907_0002'
down_revision='20260907_0001'
branch_labels=None
depends_on=None

job_status=sa.Enum('queued','running','succeeded','retry','dead','canceled',name='jobstatus')

def upgrade():
    op.create_table('background_jobs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=True),
        sa.Column('store_id',sa.String(36),sa.ForeignKey('stores.id',ondelete='CASCADE'),nullable=True),
        sa.Column('job_type',sa.String(80),nullable=False),
        sa.Column('idempotency_key',sa.String(255),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('status',job_status,nullable=False,server_default='queued'),
        sa.Column('priority',sa.Integer(),nullable=False,server_default='100'),
        sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('max_attempts',sa.Integer(),nullable=False,server_default='5'),
        sa.Column('available_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('locked_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('locked_by',sa.String(120),nullable=False,server_default=''),
        sa.Column('last_error',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('finished_at',sa.DateTime(timezone=True),nullable=True),
        sa.UniqueConstraint('idempotency_key',name='uq_background_job_idempotency'))
    for col in ('workspace_id','store_id','job_type','status','priority','available_at','locked_at','locked_by','created_at'):
        op.create_index(f'ix_background_jobs_{col}','background_jobs',[col])
    op.create_index('ix_background_jobs_claim','background_jobs',['status','available_at','priority','created_at'])

def downgrade():
    op.drop_table('background_jobs')
    job_status.drop(op.get_bind(),checkfirst=True)
