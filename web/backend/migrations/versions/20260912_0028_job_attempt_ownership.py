"""job heartbeat and attempt ownership

Revision ID: 20260912_0028
Revises: 20260910_0027
"""
from alembic import op
import sqlalchemy as sa


revision = "20260912_0028"
down_revision = "20260910_0027"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("background_jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("background_jobs", sa.Column("attempt_id", sa.String(length=36), nullable=False, server_default=""))
    op.create_index("ix_background_jobs_heartbeat_at", "background_jobs", ["heartbeat_at"])
    op.create_index("ix_background_jobs_attempt_id", "background_jobs", ["attempt_id"])


def downgrade():
    op.drop_index("ix_background_jobs_attempt_id", table_name="background_jobs")
    op.drop_index("ix_background_jobs_heartbeat_at", table_name="background_jobs")
    op.drop_column("background_jobs", "attempt_id")
    op.drop_column("background_jobs", "heartbeat_at")
