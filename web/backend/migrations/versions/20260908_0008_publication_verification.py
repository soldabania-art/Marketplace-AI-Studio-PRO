"""add post-write Wildberries verification

Revision ID: 20260908_0008
Revises: 20260908_0007
"""
from alembic import op
import sqlalchemy as sa

revision='20260908_0008'
down_revision='20260908_0007'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('card_publications',sa.Column('verification_status',sa.String(length=32),nullable=False,server_default='not_checked'))
    op.add_column('card_publications',sa.Column('verification_payload',sa.JSON(),nullable=False,server_default='{}'))
    op.add_column('card_publications',sa.Column('verification_attempt_count',sa.Integer(),nullable=False,server_default='0'))
    op.add_column('card_publications',sa.Column('last_verified_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('card_publications',sa.Column('verified_at',sa.DateTime(timezone=True),nullable=True))
    for column in ('verification_status','last_verified_at','verified_at'):
        op.create_index(f'ix_card_publications_{column}','card_publications',[column])


def downgrade():
    for column in ('verified_at','last_verified_at','verification_status'):
        op.drop_index(f'ix_card_publications_{column}',table_name='card_publications')
    for column in ('verified_at','last_verified_at','verification_attempt_count','verification_payload','verification_status'):
        op.drop_column('card_publications',column)
