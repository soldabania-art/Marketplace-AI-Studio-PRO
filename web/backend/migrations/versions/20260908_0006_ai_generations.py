"""persist every AI generation

Revision ID: 20260908_0006
Revises: 20260907_0005
"""
from alembic import op
import sqlalchemy as sa

revision='20260908_0006'
down_revision='20260907_0005'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('ai_generations',
        sa.Column('id',sa.String(length=36),primary_key=True),
        sa.Column('workspace_id',sa.String(length=36),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
        sa.Column('store_id',sa.String(length=36),sa.ForeignKey('stores.id',ondelete='CASCADE'),nullable=False),
        sa.Column('user_id',sa.String(length=36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('feature',sa.String(length=80),nullable=False),
        sa.Column('subject_type',sa.String(length=40),nullable=False,server_default='product'),
        sa.Column('subject_id',sa.String(length=160),nullable=False),
        sa.Column('input_hash',sa.String(length=64),nullable=False),
        sa.Column('fact_set_sha256',sa.String(length=64),nullable=False,server_default=''),
        sa.Column('model',sa.String(length=120),nullable=False,server_default=''),
        sa.Column('status',sa.Enum('pending','completed','failed',name='generationstatus'),nullable=False),
        sa.Column('input_payload',sa.JSON(),nullable=False),
        sa.Column('result_payload',sa.JSON(),nullable=False),
        sa.Column('token_usage',sa.JSON(),nullable=False),
        sa.Column('estimated_cost_microusd',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('provider_response_id',sa.String(length=160),nullable=False,server_default=''),
        sa.Column('error',sa.Text(),nullable=False,server_default=''),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('completed_at',sa.DateTime(timezone=True),nullable=True),
    )
    for column in ('workspace_id','store_id','user_id','feature','subject_type','subject_id','input_hash','fact_set_sha256','status','created_at','completed_at'):
        op.create_index(f'ix_ai_generations_{column}','ai_generations',[column])


def downgrade():
    op.drop_table('ai_generations')
