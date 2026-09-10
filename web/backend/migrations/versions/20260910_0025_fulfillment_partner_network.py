"""fulfillment partner network foundation

Revision ID: 20260910_0025
Revises: 20260910_0024
"""
from alembic import op
import sqlalchemy as sa

revision='20260910_0025'
down_revision='20260910_0024'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('fulfillment_partners',sa.Column('id',sa.String(length=36),nullable=False),sa.Column('code',sa.String(length=64),nullable=False),sa.Column('name',sa.String(length=160),nullable=False),sa.Column('countries',sa.JSON(),nullable=False),sa.Column('integration_mode',sa.String(length=32),nullable=False),sa.Column('capabilities',sa.JSON(),nullable=False),sa.Column('status',sa.String(length=24),nullable=False),sa.Column('documentation_url',sa.String(length=500),nullable=False),sa.Column('security_reviewed_at',sa.DateTime(timezone=True),nullable=True),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.PrimaryKeyConstraint('id'),sa.UniqueConstraint('code',name='uq_fulfillment_partner_code'))
    for column in ('code','integration_mode','status','security_reviewed_at','created_at','updated_at'):op.create_index(f'ix_fulfillment_partners_{column}','fulfillment_partners',[column])
    op.create_table('fulfillment_connections',sa.Column('id',sa.String(length=36),nullable=False),sa.Column('workspace_id',sa.String(length=36),nullable=False),sa.Column('store_id',sa.String(length=36),nullable=False),sa.Column('partner_id',sa.String(length=36),nullable=False),sa.Column('client_reference',sa.String(length=160),nullable=False),sa.Column('secret_reference',sa.String(length=160),nullable=False),sa.Column('status',sa.String(length=24),nullable=False),sa.Column('enabled_capabilities',sa.JSON(),nullable=False),sa.Column('verified_at',sa.DateTime(timezone=True),nullable=True),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],ondelete='CASCADE'),sa.ForeignKeyConstraint(['store_id'],['stores.id'],ondelete='CASCADE'),sa.ForeignKeyConstraint(['partner_id'],['fulfillment_partners.id'],ondelete='RESTRICT'),sa.PrimaryKeyConstraint('id'),sa.UniqueConstraint('store_id','partner_id',name='uq_fulfillment_connection_store_partner'))
    for column in ('workspace_id','store_id','partner_id','status','verified_at','created_at','updated_at'):op.create_index(f'ix_fulfillment_connections_{column}','fulfillment_connections',[column])

def downgrade():op.drop_table('fulfillment_connections');op.drop_table('fulfillment_partners')
