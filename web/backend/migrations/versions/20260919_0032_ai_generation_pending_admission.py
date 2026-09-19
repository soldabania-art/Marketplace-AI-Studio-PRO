"""enforce one active admission for an identical AI generation

Revision ID: 20260919_0032
Revises: 20260914_0031_backend_heads
"""

from alembic import op
import sqlalchemy as sa


revision = "20260919_0032"
down_revision = "20260914_0031_backend_heads"
branch_labels = None
depends_on = None


_KEY_COLUMNS = "store_id, feature, subject_type, subject_id, input_hash, fact_set_sha256, model"
_INDEX_NAME = "uq_ai_generation_pending_admission"


def upgrade() -> None:
    # Refuse to silently alter existing history. An operator must first resolve
    # active duplicate work deliberately, because either row may own a paid call.
    duplicates = op.get_bind().execute(sa.text(f"""
        SELECT count(*) FROM (
            SELECT 1
            FROM ai_generations
            WHERE status = 'pending'
            GROUP BY {_KEY_COLUMNS}
            HAVING count(*) > 1
        ) AS pending_duplicate_groups
    """)).scalar_one()
    if duplicates:
        raise RuntimeError(
            f"Cannot enforce AI pending admission: {duplicates} duplicate pending generation group(s) require manual reconciliation."
        )

    op.create_index(
        _INDEX_NAME,
        "ai_generations",
        _KEY_COLUMNS.split(", "),
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name="ai_generations")
