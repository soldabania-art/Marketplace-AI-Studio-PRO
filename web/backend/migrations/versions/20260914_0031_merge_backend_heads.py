"""merge WB capability, account mail, and platform staff heads

Revision ID: 20260914_0031_backend_heads
Revises: 20260913_0030, 20260913_t09b_email_delivery, 20260913_ctrl01_staff
"""


revision = "20260914_0031_backend_heads"
down_revision = (
    "20260913_0030",
    "20260913_t09b_email_delivery",
    "20260913_ctrl01_staff",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Join the independently reviewed schema branches without changing data."""


def downgrade() -> None:
    """Split the graph back into its three independently reversible heads."""
