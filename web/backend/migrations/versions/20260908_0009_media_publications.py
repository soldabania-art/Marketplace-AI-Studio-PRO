"""add separately approved media publications

Revision ID: 20260908_0009
Revises: 20260908_0008
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision='20260908_0009'
down_revision='20260908_0008'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table(
        'media_publications',
        sa.Column('id',sa.String(length=36),primary_key=True),
        sa.Column('workspace_id',sa.String(length=36),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
        sa.Column('store_id',sa.String(length=36),sa.ForeignKey('stores.id',ondelete='CASCADE'),nullable=False),
        sa.Column('user_id',sa.String(length=36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('generation_id',sa.String(length=36),sa.ForeignKey('ai_generations.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('marketplace',sa.String(length=32),nullable=False,server_default='wildberries'),
        sa.Column('subject_id',sa.String(length=160),nullable=False),
        sa.Column('status',postgresql.ENUM('prepared','submitting','submitted','failed','stale',name='publicationstatus',create_type=False),nullable=False,server_default='prepared'),
        sa.Column('fact_set_sha256',sa.String(length=64),nullable=False),
        sa.Column('source_card_sha256',sa.String(length=64),nullable=False),
        sa.Column('payload_sha256',sa.String(length=64),nullable=False),
        sa.Column('source_payload',sa.JSON(),nullable=False,server_default='{}'),
        sa.Column('asset_payload',sa.JSON(),nullable=False,server_default='{}'),
        sa.Column('diff_payload',sa.JSON(),nullable=False,server_default='{}'),
        sa.Column('provider_response',sa.JSON(),nullable=False,server_default='{}'),
        sa.Column('error',sa.Text(),nullable=False,server_default=''),
        sa.Column('attempt_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('verification_status',sa.String(length=32),nullable=False,server_default='not_checked'),
        sa.Column('verification_payload',sa.JSON(),nullable=False,server_default='{}'),
        sa.Column('verification_attempt_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('last_verified_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('verified_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('approved_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('submitted_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
    )
    for column in ('workspace_id','store_id','user_id','generation_id','marketplace','subject_id','status','fact_set_sha256','source_card_sha256','payload_sha256','verification_status','last_verified_at','verified_at','approved_at','submitted_at','created_at'):
        op.create_index(f'ix_media_publications_{column}','media_publications',[column])


def downgrade():
    op.drop_table('media_publications')
