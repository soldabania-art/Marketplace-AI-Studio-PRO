"""fence concurrent WB capability checks for one credentials version

Revision ID: 20260913_0030
Revises: 20260913_0029
"""
from alembic import op
import sqlalchemy as sa


revision = "20260913_0030"
down_revision = "20260913_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "marketplace_connections",
        sa.Column("capability_check_generation", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("marketplace_connections", "capability_check_generation")
