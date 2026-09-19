"""durable account email deliveries

Revision ID: 20260913_t09b_email_delivery
Revises: 20260912_0028
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260913_t09b_email_delivery"
down_revision = "20260912_0028"
branch_labels = None
depends_on = None

delivery_status = sa.Enum("queued", "provider_accepted", "failed", "outcome_unknown", name="emaildeliverystatus")
token_purpose = postgresql.ENUM("verify_email", "reset_password", name="accounttokenpurpose", create_type=False)


def upgrade():
    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_id", sa.String(36), sa.ForeignKey("account_action_tokens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", token_purpose, nullable=False),
        sa.Column("recipient", sa.String(320), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="resend"),
        sa.Column("provider_idempotency_key", sa.String(255), nullable=False),
        sa.Column("provider_payload_sha256", sa.String(64), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("status", delivery_status, nullable=False, server_default="queued"),
        sa.Column("submit_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unknown_outcomes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("may_have_been_accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("submitting_attempt_id", sa.String(36), nullable=False, server_default=""),
        sa.Column("submitting_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(160), nullable=False, server_default=""),
        sa.Column("last_error", sa.String(500), nullable=False, server_default=""),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("token_id", name="uq_email_delivery_token"),
        sa.UniqueConstraint("provider", "provider_idempotency_key", name="uq_email_delivery_provider_key"),
    )
    for column in ("user_id", "token_id", "purpose", "provider", "status", "submitting_attempt_id", "first_submitted_at", "provider_message_id", "expires_at", "provider_accepted_at", "failed_at", "created_at"):
        op.create_index(f"ix_email_deliveries_{column}", "email_deliveries", [column])


def downgrade():
    op.drop_table("email_deliveries")
    delivery_status.drop(op.get_bind(), checkfirst=True)
