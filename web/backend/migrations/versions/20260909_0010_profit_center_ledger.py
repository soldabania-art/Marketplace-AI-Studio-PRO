"""add source financial ledger and confirmed product costs

Revision ID: 20260909_0010
Revises: 20260908_0009
"""
from alembic import op
import sqlalchemy as sa

revision='20260909_0010'
down_revision='20260908_0009'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table(
        'marketplace_financial_lines',
        sa.Column('id',sa.String(length=36),primary_key=True),
        sa.Column('store_id',sa.String(length=36),sa.ForeignKey('stores.id',ondelete='CASCADE'),nullable=False),
        sa.Column('marketplace',sa.String(length=32),nullable=False,server_default='wildberries'),
        sa.Column('source_line_id',sa.String(length=80),nullable=False),
        sa.Column('report_id',sa.String(length=80),nullable=False,server_default=''),
        sa.Column('nm_id',sa.Integer(),nullable=True),
        sa.Column('vendor_code',sa.String(length=255),nullable=False,server_default=''),
        sa.Column('title',sa.String(length=500),nullable=False,server_default=''),
        sa.Column('operation',sa.String(length=255),nullable=False,server_default=''),
        sa.Column('document_type',sa.String(length=80),nullable=False,server_default=''),
        sa.Column('event_date',sa.String(length=40),nullable=False,server_default=''),
        sa.Column('quantity',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('gross_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('payout_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('commission_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('logistics_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('acquiring_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('storage_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('acceptance_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('penalty_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('deduction_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('additional_payment_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('source_sha256',sa.String(length=64),nullable=False),
        sa.Column('source_payload',sa.JSON(),nullable=False,server_default='{}'),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint('store_id','marketplace','source_line_id',name='uq_financial_line_source'),
    )
    for column in ('store_id','marketplace','source_line_id','report_id','nm_id','vendor_code','operation','document_type','event_date','source_sha256','created_at','updated_at'):
        op.create_index(f'ix_marketplace_financial_lines_{column}','marketplace_financial_lines',[column])
    op.create_table(
        'product_cost_profiles',
        sa.Column('id',sa.String(length=36),primary_key=True),
        sa.Column('store_id',sa.String(length=36),sa.ForeignKey('stores.id',ondelete='CASCADE'),nullable=False),
        sa.Column('marketplace',sa.String(length=32),nullable=False,server_default='wildberries'),
        sa.Column('nm_id',sa.Integer(),nullable=False),
        sa.Column('cogs_kopecks',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('confirmed_by_user_id',sa.String(length=36),sa.ForeignKey('users.id',ondelete='RESTRICT'),nullable=False),
        sa.Column('source',sa.String(length=40),nullable=False,server_default='manual'),
        sa.Column('confirmed_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.UniqueConstraint('store_id','marketplace','nm_id',name='uq_product_cost_store_marketplace_nm'),
    )
    for column in ('store_id','marketplace','nm_id','confirmed_by_user_id','confirmed_at','created_at','updated_at'):
        op.create_index(f'ix_product_cost_profiles_{column}','product_cost_profiles',[column])


def downgrade():
    op.drop_table('product_cost_profiles')
    op.drop_table('marketplace_financial_lines')
