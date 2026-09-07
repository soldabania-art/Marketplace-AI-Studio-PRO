"""managed schema baseline and store scoping

Revision ID: 20260907_0001
Revises:
Create Date: 2026-09-07

This revision is intentionally defensive: it can initialize a fresh database or
upgrade the pre-Alembic schema that was previously created with metadata.create_all().
"""

from alembic import op
import sqlalchemy as sa

revision = '20260907_0001'
down_revision = None
branch_labels = None
depends_on = None


def _tables(bind):
    return set(sa.inspect(bind).get_table_names())


def _columns(bind, table):
    return {c['name'] for c in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table):
    return {i['name'] for i in sa.inspect(bind).get_indexes(table)}


def _unique_names(bind, table):
    return {u.get('name') for u in sa.inspect(bind).get_unique_constraints(table)}


def upgrade():
    bind = op.get_bind()
    tables = _tables(bind)

    membership_role = sa.Enum('owner','admin','analyst','operator',name='membershiprole')
    subscription_status = sa.Enum('trial','active','past_due','canceled',name='subscriptionstatus')
    token_purpose = sa.Enum('verify_email','reset_password',name='accounttokenpurpose')

    if 'users' not in tables:
        op.create_table('users',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('email',sa.String(320),nullable=False),
            sa.Column('password_hash',sa.String(255),nullable=False),
            sa.Column('full_name',sa.String(160),nullable=False,server_default=''),
            sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()),
            sa.Column('email_verified',sa.Boolean(),nullable=False,server_default=sa.false()),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.UniqueConstraint('email',name='uq_users_email'))
        op.create_index('ix_users_email','users',['email'],unique=True)
        tables.add('users')

    if 'workspaces' not in tables:
        op.create_table('workspaces',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('name',sa.String(160),nullable=False),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
        tables.add('workspaces')

    if 'stores' not in tables:
        op.create_table('stores',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
            sa.Column('name',sa.String(160),nullable=False),
            sa.Column('client_name',sa.String(160),nullable=False,server_default=''),
            sa.Column('is_active',sa.Boolean(),nullable=False,server_default=sa.true()),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.UniqueConstraint('workspace_id','name',name='uq_store_workspace_name'))
        op.create_index('ix_stores_workspace_id','stores',['workspace_id'])
        op.create_index('ix_stores_is_active','stores',['is_active'])
        tables.add('stores')

    if 'memberships' not in tables:
        op.create_table('memberships',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
            sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
            sa.Column('role',membership_role,nullable=False,server_default='owner'),
            sa.UniqueConstraint('user_id','workspace_id',name='uq_membership_user_workspace'))
        op.create_index('ix_memberships_user_id','memberships',['user_id'])
        op.create_index('ix_memberships_workspace_id','memberships',['workspace_id'])
        tables.add('memberships')

    if 'subscriptions' not in tables:
        op.create_table('subscriptions',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('workspace_id',sa.String(36),sa.ForeignKey('workspaces.id',ondelete='CASCADE'),nullable=False),
            sa.Column('plan_code',sa.String(40),nullable=False,server_default='trial'),
            sa.Column('status',subscription_status,nullable=False,server_default='trial'),
            sa.Column('provider',sa.String(40)),
            sa.Column('provider_customer_id',sa.String(160)),
            sa.Column('provider_subscription_id',sa.String(160)),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
        op.create_index('ix_subscriptions_workspace_id','subscriptions',['workspace_id'])
        tables.add('subscriptions')

    if 'legal_consents' not in tables:
        op.create_table('legal_consents',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
            sa.Column('document_code',sa.String(80),nullable=False),
            sa.Column('document_version',sa.String(40),nullable=False),
            sa.Column('accepted',sa.Boolean(),nullable=False,server_default=sa.true()),
            sa.Column('source',sa.String(80),nullable=False,server_default='web'),
            sa.Column('accepted_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.UniqueConstraint('user_id','document_code','document_version',name='uq_legal_consent_version'))
        op.create_index('ix_legal_consents_user_id','legal_consents',['user_id'])
        op.create_index('ix_legal_consents_document_code','legal_consents',['document_code'])
        tables.add('legal_consents')

    if 'account_action_tokens' not in tables:
        op.create_table('account_action_tokens',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
            sa.Column('purpose',token_purpose,nullable=False),
            sa.Column('token_hash',sa.String(64),nullable=False,unique=True),
            sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
            sa.Column('used_at',sa.DateTime(timezone=True)),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
        op.create_index('ix_account_action_tokens_user_id','account_action_tokens',['user_id'])
        op.create_index('ix_account_action_tokens_purpose','account_action_tokens',['purpose'])
        op.create_index('ix_account_action_tokens_token_hash','account_action_tokens',['token_hash'],unique=True)
        op.create_index('ix_account_action_tokens_expires_at','account_action_tokens',['expires_at'])
        tables.add('account_action_tokens')

    if 'user_sessions' not in tables:
        op.create_table('user_sessions',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
            sa.Column('user_agent',sa.String(320),nullable=False,server_default=''),
            sa.Column('ip_hash',sa.String(64),nullable=False,server_default=''),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.Column('last_seen_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
            sa.Column('revoked_at',sa.DateTime(timezone=True)))
        op.create_index('ix_user_sessions_user_id','user_sessions',['user_id'])
        op.create_index('ix_user_sessions_expires_at','user_sessions',['expires_at'])
        op.create_index('ix_user_sessions_revoked_at','user_sessions',['revoked_at'])
        tables.add('user_sessions')

    if 'security_events' not in tables:
        op.create_table('security_events',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE')),
            sa.Column('event_type',sa.String(80),nullable=False),
            sa.Column('success',sa.Boolean(),nullable=False,server_default=sa.true()),
            sa.Column('subject_hash',sa.String(64),nullable=False,server_default=''),
            sa.Column('ip_hash',sa.String(64),nullable=False,server_default=''),
            sa.Column('user_agent',sa.String(320),nullable=False,server_default=''),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
        for name,col in [('ix_security_events_user_id','user_id'),('ix_security_events_event_type','event_type'),('ix_security_events_success','success'),('ix_security_events_subject_hash','subject_hash'),('ix_security_events_ip_hash','ip_hash'),('ix_security_events_created_at','created_at')]:
            op.create_index(name,'security_events',[col])
        tables.add('security_events')

    if 'push_subscriptions' not in tables:
        op.create_table('push_subscriptions',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
            sa.Column('endpoint',sa.String(2048),nullable=False,unique=True),
            sa.Column('p256dh',sa.String(512),nullable=False),
            sa.Column('auth',sa.String(512),nullable=False),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
        op.create_index('ix_push_subscriptions_user_id','push_subscriptions',['user_id'])
        tables.add('push_subscriptions')

    if 'fbo_watches' not in tables:
        op.create_table('fbo_watches',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
            sa.Column('store_id',sa.String(36),sa.ForeignKey('stores.id',ondelete='CASCADE')),
            sa.Column('marketplace',sa.String(32),nullable=False,server_default='wildberries'),
            sa.Column('warehouse_filter',sa.String(500),nullable=False,server_default=''),
            sa.Column('free_only',sa.Boolean(),nullable=False,server_default=sa.false()),
            sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.true()),
            sa.Column('last_slot_fingerprint',sa.String(64),nullable=False,server_default=''),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.Column('last_checked_at',sa.DateTime(timezone=True)),
            sa.UniqueConstraint('store_id','marketplace',name='uq_fbo_watch_store_marketplace'))
        op.create_index('ix_fbo_watches_user_id','fbo_watches',['user_id'])
        op.create_index('ix_fbo_watches_store_id','fbo_watches',['store_id'])
        op.create_index('ix_fbo_watches_enabled','fbo_watches',['enabled'])
        tables.add('fbo_watches')
    elif 'store_id' not in _columns(bind,'fbo_watches'):
        with op.batch_alter_table('fbo_watches') as batch:
            batch.add_column(sa.Column('store_id',sa.String(36),nullable=True))
            batch.create_foreign_key('fk_fbo_watches_store_id_stores','stores',['store_id'],['id'],ondelete='CASCADE')
            batch.create_index('ix_fbo_watches_store_id',['store_id'])

    if 'marketplace_connections' not in tables:
        op.create_table('marketplace_connections',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
            sa.Column('store_id',sa.String(36),sa.ForeignKey('stores.id',ondelete='CASCADE')),
            sa.Column('marketplace',sa.String(32),nullable=False),
            sa.Column('encrypted_token',sa.String(4096),nullable=False),
            sa.Column('token_hint',sa.String(24),nullable=False,server_default=''),
            sa.Column('enabled',sa.Boolean(),nullable=False,server_default=sa.true()),
            sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
            sa.UniqueConstraint('store_id','marketplace',name='uq_marketplace_connection_store_marketplace'))
        op.create_index('ix_marketplace_connections_user_id','marketplace_connections',['user_id'])
        op.create_index('ix_marketplace_connections_store_id','marketplace_connections',['store_id'])
        op.create_index('ix_marketplace_connections_marketplace','marketplace_connections',['marketplace'])
        op.create_index('ix_marketplace_connections_enabled','marketplace_connections',['enabled'])
        tables.add('marketplace_connections')
    elif 'store_id' not in _columns(bind,'marketplace_connections'):
        with op.batch_alter_table('marketplace_connections') as batch:
            batch.add_column(sa.Column('store_id',sa.String(36),nullable=True))
            batch.create_foreign_key('fk_marketplace_connections_store_id_stores','stores',['store_id'],['id'],ondelete='CASCADE')
            batch.create_index('ix_marketplace_connections_store_id',['store_id'])

    # Backfill a deterministic default store for every workspace that does not have one.
    workspaces = bind.execute(sa.text('SELECT id, name FROM workspaces')).mappings().all()
    for workspace in workspaces:
        existing = bind.execute(sa.text('SELECT id FROM stores WHERE workspace_id=:wid LIMIT 1'),{'wid':workspace['id']}).scalar()
        if not existing:
            import uuid
            store_id = str(uuid.uuid4())
            bind.execute(sa.text('INSERT INTO stores (id, workspace_id, name, client_name, is_active) VALUES (:id,:wid,:name,:client,true)'),{
                'id':store_id,'wid':workspace['id'],'name':'Основной магазин','client':workspace['name'] or ''})

    # Attach legacy connections/watches to the first store in one of the actor's workspaces.
    for table in ('marketplace_connections','fbo_watches'):
        if table in _tables(bind) and 'store_id' in _columns(bind,table):
            rows = bind.execute(sa.text(f'SELECT id, user_id FROM {table} WHERE store_id IS NULL')).mappings().all()
            for row in rows:
                store_id = bind.execute(sa.text('''
                    SELECT s.id FROM stores s
                    JOIN memberships m ON m.workspace_id=s.workspace_id
                    WHERE m.user_id=:uid
                    ORDER BY s.created_at, s.id LIMIT 1
                '''),{'uid':row['user_id']}).scalar()
                if store_id:
                    bind.execute(sa.text(f'UPDATE {table} SET store_id=:sid WHERE id=:id'),{'sid':store_id,'id':row['id']})

    # Add store-scoped uniqueness for upgraded legacy databases when absent.
    if bind.dialect.name != 'sqlite':
        if 'uq_marketplace_connection_store_marketplace' not in _unique_names(bind,'marketplace_connections'):
            op.create_unique_constraint('uq_marketplace_connection_store_marketplace','marketplace_connections',['store_id','marketplace'])
        if 'uq_fbo_watch_store_marketplace' not in _unique_names(bind,'fbo_watches'):
            op.create_unique_constraint('uq_fbo_watch_store_marketplace','fbo_watches',['store_id','marketplace'])


def downgrade():
    # This is the first managed production baseline. Automatic destructive downgrade is
    # intentionally disabled; restore from a tested backup instead.
    raise RuntimeError('Downgrade of the managed baseline is intentionally disabled')
