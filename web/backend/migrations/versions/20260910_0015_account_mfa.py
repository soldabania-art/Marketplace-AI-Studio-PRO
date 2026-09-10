"""account multi-factor authentication

Revision ID: 20260910_0015
Revises: 20260909_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20260910_0015"
down_revision = "20260909_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_sessions", sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "user_mfa",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recovery_code_hashes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("last_totp_step", sa.Integer(), nullable=True),
        sa.Column("pending_created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_mfa_enabled", "user_mfa", ["enabled"])
    op.create_table(
        "mfa_login_challenges",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_mfa_login_challenges_token_hash"),
    )
    for column in ("user_id", "token_hash", "expires_at", "used_at", "created_at"):
        op.create_index(f"ix_mfa_login_challenges_{column}", "mfa_login_challenges", [column])


def downgrade():
    op.drop_table("mfa_login_challenges")
    op.drop_table("user_mfa")
    op.drop_column("user_sessions", "mfa_verified_at")
