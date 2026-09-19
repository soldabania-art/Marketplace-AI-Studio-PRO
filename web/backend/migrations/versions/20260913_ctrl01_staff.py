"""persist platform staff roles and one-time bootstrap state

Revision ID: 20260913_ctrl01_staff
Revises: 20260912_0028
"""
from alembic import op
import sqlalchemy as sa


revision = "20260913_ctrl01_staff"
down_revision = "20260912_0028"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_bootstrap_states",
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "platform_staff_roles",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=15), nullable=False),
        sa.Column("granted_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(length=36), nullable=True),
        sa.CheckConstraint("role IN ('owner', 'project_manager')", name="platform_staff_role_name"),
        sa.ForeignKeyConstraint(["granted_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_platform_staff_roles_role", "platform_staff_roles", ["role"])
    op.create_index("ix_platform_staff_roles_granted_by_user_id", "platform_staff_roles", ["granted_by_user_id"])
    op.create_index("ix_platform_staff_roles_revoked_at", "platform_staff_roles", ["revoked_at"])
    op.create_index("ix_platform_staff_roles_revoked_by_user_id", "platform_staff_roles", ["revoked_by_user_id"])


def downgrade():
    op.drop_index("ix_platform_staff_roles_revoked_by_user_id", table_name="platform_staff_roles")
    op.drop_index("ix_platform_staff_roles_revoked_at", table_name="platform_staff_roles")
    op.drop_index("ix_platform_staff_roles_granted_by_user_id", table_name="platform_staff_roles")
    op.drop_index("ix_platform_staff_roles_role", table_name="platform_staff_roles")
    op.drop_table("platform_staff_roles")
    op.drop_table("platform_bootstrap_states")
