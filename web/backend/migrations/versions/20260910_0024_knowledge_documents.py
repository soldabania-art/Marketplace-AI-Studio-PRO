"""versioned product-help knowledge documents

Revision ID: 20260910_0024
Revises: 20260910_0023
"""
from alembic import op
import sqlalchemy as sa

revision='20260910_0024'
down_revision='20260910_0023'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('knowledge_documents',
        sa.Column('id',sa.String(length=36),nullable=False),sa.Column('slug',sa.String(length=120),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('title',sa.String(length=240),nullable=False),sa.Column('body',sa.Text(),nullable=False),sa.Column('source_url',sa.String(length=500),nullable=False),sa.Column('source_type',sa.String(length=40),nullable=False),sa.Column('audience',sa.String(length=40),nullable=False),sa.Column('status',sa.String(length=24),nullable=False),sa.Column('product_version',sa.String(length=40),nullable=False),sa.Column('checksum_sha256',sa.String(length=64),nullable=False),sa.Column('reviewed_by_user_id',sa.String(length=36),nullable=True),sa.Column('reviewed_at',sa.DateTime(timezone=True),nullable=True),sa.Column('effective_at',sa.DateTime(timezone=True),nullable=True),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=True),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.text('CURRENT_TIMESTAMP'),nullable=False),sa.ForeignKeyConstraint(['reviewed_by_user_id'],['users.id'],ondelete='RESTRICT'),sa.PrimaryKeyConstraint('id'),sa.UniqueConstraint('slug','version',name='uq_knowledge_document_slug_version'))
    for column in ('slug','status','source_type','audience','checksum_sha256','reviewed_by_user_id','reviewed_at','effective_at','expires_at','created_at','updated_at'):op.create_index(f'ix_knowledge_documents_{column}','knowledge_documents',[column])

def downgrade():op.drop_table('knowledge_documents')
