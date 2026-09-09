"""add advertising ledger and confirmed tax profile

Revision ID: 20260909_0011
Revises: 20260909_0010
"""
from alembic import op
import sqlalchemy as sa

revision='20260909_0011'
down_revision='20260909_0010'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table(
        'marketplace_advertising_lines',
        sa.Column('id',sa.String(length=36),primary_key=True),
        sa.Column('store_id',sa.String(length=36),sa.ForeignKey('stores.id',ondelete='CASCADE'),nullable=False),
        sa.Column('marketplace',sa.String(length=32),nullable=False,server_default='wildberries'),
        sa.Column('source_line_id',sa.String(length=160),nullable=False),
        sa.Column('campaign_id',sa.Integer(),nullable=False),
        sa.Column('campaign_name',sa.String(length=500),nullable=False,server_default=''),
        sa.Column('nm_id',sa.Integer(),nullable=True),
        sa.Column('event_date',sa.String(length=10),nullable=False),
        sa.Column('spend_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('attributed_revenue_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('views',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('clicks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('orders',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('units',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('source_sha256',sa.String(length=64),nullable=False),
        sa.Column('source_payload',sa.JSON(),nullable=False,server_default='{}'),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint('store_id','marketplace','source_line_id',name='uq_advertising_line_source'),
    )
    for column in ('store_id','marketplace','source_line_id','campaign_id','nm_id','event_date','source_sha256','created_at','updated_at'):
        op.create_index(f'ix_marketplace_advertising_lines_{column}','marketplace_advertising_lines',[column])
    op.create_table(
        'store_tax_profiles',
        sa.Column('id',sa.String(length=36),primary_key=True),
        sa.Column('store_id',sa.String(length=36),sa.ForeignKey('stores.id',ondelete='CASCADE'),nullable=False),
        sa.Column('marketplace',sa.String(length=32),nullable=False,server_default='wildberries'),
        sa.Column('basis',sa.String(length=40),nullable=False),
        sa.Column('rate_bps',sa.Integer(),nullable=False),
        sa.Column('note',sa.String(length=500),nullable=False,server_default=''),
        sa.Column('confirmed_by_user_id',sa.String(length=36),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('confirmed_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint('store_id','marketplace',name='uq_tax_profile_store_marketplace'),
    )
    for column in ('store_id','marketplace','confirmed_by_user_id','confirmed_at','created_at','updated_at'):
        op.create_index(f'ix_store_tax_profiles_{column}','store_tax_profiles',[column])


def downgrade():
    op.drop_table('store_tax_profiles')
    op.drop_table('marketplace_advertising_lines')
