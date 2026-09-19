"""store-scoped WB capability results and credential fencing

Revision ID: 20260913_0029
Revises: 20260912_0028
"""
from alembic import op
import sqlalchemy as sa


revision = "20260913_0029"
down_revision = "20260912_0028"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "marketplace_connections",
        sa.Column("credentials_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "marketplace_connections",
        sa.Column("capability_results", sa.JSON(), nullable=True),
    )
    op.add_column(
        "marketplace_connections",
        sa.Column("capabilities_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_marketplace_connections_capabilities_checked_at",
        "marketplace_connections",
        ["capabilities_checked_at"],
    )


def downgrade():
    op.drop_index(
        "ix_marketplace_connections_capabilities_checked_at",
        table_name="marketplace_connections",
    )
    op.drop_column("marketplace_connections", "capabilities_checked_at")
    op.drop_column("marketplace_connections", "capability_results")
    op.drop_column("marketplace_connections", "credentials_version")
