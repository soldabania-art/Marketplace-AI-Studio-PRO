"""fulfillment facilities registry

Revision ID: 20260910_0026
Revises: 20260910_0025
"""
from alembic import op
import sqlalchemy as sa

revision='20260910_0026'
down_revision='20260910_0025'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('fulfillment_facilities',sa.Column('id',sa.String(length=36),nullable=False),sa.Column('partner_id',sa.String(length=36),nullable=False),sa.Column('external_id',sa.String(length=120),nullable=False),sa.Column('name',sa.String(length=200),nullable=False),sa.Column('country_code',sa.String(length=2),nullable=False),sa.Column('city',sa.String(length=120),nullable=False),sa.Column('timezone_name',sa.String(length=64),nullable=False),sa.Column('service_modes',sa.JSON(),nullable=False),sa.Column('marketplace_codes',sa.JSON(),nullable=False),sa.Column('active',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.ForeignKeyConstraint(['partner_id'],['fulfillment_partners.id'],ondelete='CASCADE'),sa.PrimaryKeyConstraint('id'),sa.UniqueConstraint('partner_id','external_id',name='uq_fulfillment_facility_partner_external'))
    for column in ('partner_id','external_id','country_code','city','active','created_at','updated_at'):op.create_index(f'ix_fulfillment_facilities_{column}','fulfillment_facilities',[column])

def downgrade():op.drop_table('fulfillment_facilities')
