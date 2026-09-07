"""add persistent beginner projects

Revision ID: 20260907_0004
Revises: 20260907_0003
"""
from alembic import op
import sqlalchemy as sa

revision='20260907_0004'
down_revision='20260907_0003'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('beginner_projects',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('store_id',sa.String(36),sa.ForeignKey('stores.id',ondelete='CASCADE'),nullable=False),
        sa.Column('created_by_user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('title',sa.String(160),nullable=False,server_default='Новый товар'),
        sa.Column('stage',sa.String(40),nullable=False,server_default='facts'),
        sa.Column('state',sa.JSON(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_beginner_projects_store_id','beginner_projects',['store_id'])
    op.create_index('ix_beginner_projects_created_by_user_id','beginner_projects',['created_by_user_id'])
    op.create_index('ix_beginner_projects_stage','beginner_projects',['stage'])
    op.create_index('ix_beginner_projects_created_at','beginner_projects',['created_at'])
    op.create_index('ix_beginner_projects_updated_at','beginner_projects',['updated_at'])


def downgrade():
    op.drop_table('beginner_projects')
