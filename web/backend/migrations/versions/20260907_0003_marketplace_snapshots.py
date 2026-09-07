"""add marketplace snapshots

Revision ID: 20260907_0003
Revises: 20260907_0002
"""
from alembic import op
import sqlalchemy as sa

revision='20260907_0003'
down_revision='20260907_0002'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('marketplace_snapshots',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('store_id',sa.String(36),sa.ForeignKey('stores.id',ondelete='CASCADE'),nullable=False),
        sa.Column('marketplace',sa.String(32),nullable=False),
        sa.Column('snapshot_type',sa.String(80),nullable=False),
        sa.Column('schema_version',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('source_updated_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()))
    op.create_index('ix_marketplace_snapshots_store_id','marketplace_snapshots',['store_id'])
    op.create_index('ix_marketplace_snapshots_marketplace','marketplace_snapshots',['marketplace'])
    op.create_index('ix_marketplace_snapshots_snapshot_type','marketplace_snapshots',['snapshot_type'])
    op.create_index('ix_marketplace_snapshots_created_at','marketplace_snapshots',['created_at'])
    op.create_index('ix_marketplace_snapshots_lookup','marketplace_snapshots',['store_id','marketplace','snapshot_type','created_at'])


def downgrade():
    op.drop_table('marketplace_snapshots')
