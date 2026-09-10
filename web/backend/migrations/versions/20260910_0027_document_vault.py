"""tenant document vault

Revision ID: 20260910_0027
Revises: 20260910_0026
"""
from alembic import op
import sqlalchemy as sa

revision='20260910_0027'
down_revision='20260910_0026'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('vault_documents',sa.Column('id',sa.String(length=36),nullable=False),sa.Column('workspace_id',sa.String(length=36),nullable=False),sa.Column('store_id',sa.String(length=36),nullable=False),sa.Column('fulfillment_partner_id',sa.String(length=36),nullable=True),sa.Column('uploaded_by_user_id',sa.String(length=36),nullable=False),sa.Column('subject_type',sa.String(length=32),nullable=False),sa.Column('document_type',sa.String(length=48),nullable=False),sa.Column('display_name',sa.String(length=240),nullable=False),sa.Column('external_reference_sha256',sa.String(length=64),nullable=False),sa.Column('storage_path',sa.String(length=500),nullable=False),sa.Column('content_type',sa.String(length=120),nullable=False),sa.Column('byte_size',sa.Integer(),nullable=False),sa.Column('content_sha256',sa.String(length=64),nullable=False),sa.Column('status',sa.String(length=24),nullable=False),sa.Column('scan_status',sa.String(length=24),nullable=False),sa.Column('retention_class',sa.String(length=40),nullable=False),sa.Column('retention_until',sa.DateTime(timezone=True),nullable=True),sa.Column('legal_hold',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.Column('finalized_at',sa.DateTime(timezone=True),nullable=True),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],ondelete='CASCADE'),sa.ForeignKeyConstraint(['store_id'],['stores.id'],ondelete='CASCADE'),sa.ForeignKeyConstraint(['fulfillment_partner_id'],['fulfillment_partners.id'],ondelete='RESTRICT'),sa.ForeignKeyConstraint(['uploaded_by_user_id'],['users.id'],ondelete='RESTRICT'),sa.PrimaryKeyConstraint('id'),sa.UniqueConstraint('storage_path'))
    for column in ('workspace_id','store_id','fulfillment_partner_id','uploaded_by_user_id','subject_type','document_type','external_reference_sha256','storage_path','content_sha256','status','scan_status','retention_class','retention_until','legal_hold','created_at','finalized_at','updated_at'):op.create_index(f'ix_vault_documents_{column}','vault_documents',[column])
    op.create_table('vault_document_events',sa.Column('id',sa.String(length=36),nullable=False),sa.Column('document_id',sa.String(length=36),nullable=False),sa.Column('workspace_id',sa.String(length=36),nullable=False),sa.Column('store_id',sa.String(length=36),nullable=False),sa.Column('actor_user_id',sa.String(length=36),nullable=False),sa.Column('event_type',sa.String(length=40),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.ForeignKeyConstraint(['document_id'],['vault_documents.id'],ondelete='CASCADE'),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id'],ondelete='CASCADE'),sa.ForeignKeyConstraint(['store_id'],['stores.id'],ondelete='CASCADE'),sa.ForeignKeyConstraint(['actor_user_id'],['users.id'],ondelete='RESTRICT'),sa.PrimaryKeyConstraint('id'))
    for column in ('document_id','workspace_id','store_id','actor_user_id','event_type','created_at'):op.create_index(f'ix_vault_document_events_{column}','vault_document_events',[column])

def downgrade():op.drop_table('vault_document_events');op.drop_table('vault_documents')
