"""data health incidents

Revision ID: 20260910_0017
Revises: 20260910_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20260910_0017"
down_revision = "20260910_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "data_health_incidents",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("workspace_id", sa.String(length=36), nullable=False),
        sa.Column("store_id", sa.String(length=36), nullable=False),
        sa.Column("marketplace", sa.String(length=32), nullable=False),
        sa.Column("source_key", sa.String(length=40), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("public_message", sa.String(length=500), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("store_id", "source_key", name="uq_data_health_incident_store_source"),
        sa.UniqueConstraint("fingerprint", name="uq_data_health_incident_fingerprint"),
    )
    for column in ("workspace_id", "store_id", "marketplace", "source_key", "fingerprint", "severity", "status", "opened_at", "last_seen_at", "resolved_at"):
        op.create_index(f"ix_data_health_incidents_{column}", "data_health_incidents", [column])


def downgrade():
    op.drop_table("data_health_incidents")
