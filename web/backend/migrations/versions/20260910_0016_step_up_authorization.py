"""step-up authorization for sensitive actions

Revision ID: 20260910_0016
Revises: 20260910_0015
"""
from alembic import op
import sqlalchemy as sa

revision = "20260910_0016"
down_revision = "20260910_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user_sessions", sa.Column("step_up_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_user_sessions_step_up_verified_at", "user_sessions", ["step_up_verified_at"])


def downgrade():
    op.drop_index("ix_user_sessions_step_up_verified_at", table_name="user_sessions")
    op.drop_column("user_sessions", "step_up_verified_at")
