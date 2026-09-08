"""persist confirmed marketplace card publications

Revision ID: 20260908_0007
Revises: 20260908_0006
"""
from alembic import op
import sqlalchemy as sa

revision='20260908_0007'
down_revision='20260908_0006'
branch_labels=None
depends_on=None


def upgrade():
    publication_status=sa.Enum('prepared','submitting','submitted','failed','stale',name='publicationstatus')
    op.create_table('card_publications',
        sa.Column('id',sa.String(length=36),primary_key=True),
        sa.Column('workspace_id',sa.String(length=36),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
        sa.Column('store_id',sa.String(length=36),sa.ForeignKey('stores.id',ondelete='CASCADE'),nullable=False),
        sa.Column('user_id',sa.String(length=36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
        sa.Column('generation_id',sa.String(length=36),sa.ForeignKey('ai_generations.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('marketplace',sa.String(length=32),nullable=False,server_default='wildberries'),
        sa.Column('subject_id',sa.String(length=160),nullable=False),
        sa.Column('status',publication_status,nullable=False,server_default='prepared'),
        sa.Column('fact_set_sha256',sa.String(length=64),nullable=False),
        sa.Column('source_card_sha256',sa.String(length=64),nullable=False),
        sa.Column('payload_sha256',sa.String(length=64),nullable=False),
        sa.Column('source_payload',sa.JSON(),nullable=False),
        sa.Column('proposed_payload',sa.JSON(),nullable=False),
        sa.Column('diff_payload',sa.JSON(),nullable=False),
        sa.Column('provider_response',sa.JSON(),nullable=False),
        sa.Column('error',sa.Text(),nullable=False,server_default=''),
        sa.Column('attempt_count',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('approved_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('submitted_at',sa.DateTime(timezone=True),nullable=True),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
    )
    for column in ('workspace_id','store_id','user_id','generation_id','marketplace','subject_id','status','fact_set_sha256','source_card_sha256','payload_sha256','approved_at','submitted_at','created_at','updated_at'):
        op.create_index(f'ix_card_publications_{column}','card_publications',[column])


def downgrade():
    op.drop_table('card_publications')
    sa.Enum(name='publicationstatus').drop(op.get_bind(),checkfirst=True)
