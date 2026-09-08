"""add three day trial limits

Revision ID: 20260907_0005
Revises: 20260907_0004
"""
from alembic import op
import sqlalchemy as sa

revision='20260907_0005'
down_revision='20260907_0004'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('subscriptions',sa.Column('trial_started_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('subscriptions',sa.Column('trial_expires_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('subscriptions',sa.Column('trial_ai_cards_used',sa.Integer(),nullable=False,server_default='0'))
    op.add_column('subscriptions',sa.Column('trial_ai_cards_limit',sa.Integer(),nullable=False,server_default='5'))
    op.create_index('ix_subscriptions_trial_expires_at','subscriptions',['trial_expires_at'])


def downgrade():
    op.drop_index('ix_subscriptions_trial_expires_at',table_name='subscriptions')
    op.drop_column('subscriptions','trial_ai_cards_limit')
    op.drop_column('subscriptions','trial_ai_cards_used')
    op.drop_column('subscriptions','trial_expires_at')
    op.drop_column('subscriptions','trial_started_at')
