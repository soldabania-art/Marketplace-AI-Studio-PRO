import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PRE_ADMISSION_REVISION = "20260914_0031_backend_heads"


def _migrate(database_url: str, revision: str, *, check: bool = True):
    environment = os.environ.copy()
    environment["MARKETPLACE_DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        cwd=BACKEND_ROOT,
        env=environment,
        check=check,
        capture_output=True,
        text=True,
    )


def test_pending_duplicate_preflight_preserves_rows_for_manual_reconciliation(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'pending-duplicates.db'}"
    _migrate(database_url, PRE_ADMISSION_REVISION)
    engine = create_engine(database_url)
    with engine.begin() as connection:
        for generation_id in ("pending-1", "pending-2"):
            connection.execute(text("""
                INSERT INTO ai_generations (
                    id, workspace_id, store_id, user_id, feature, subject_type, subject_id,
                    input_hash, fact_set_sha256, model, status, input_payload, result_payload,
                    token_usage, estimated_cost_microusd, provider_response_id, error
                ) VALUES (
                    :id, 'workspace', 'store', 'user', 'review_analysis', 'product', 'snapshot',
                    'input-hash', 'fact-hash', 'model', 'pending', '{}', '{}', '{}', 0, '', ''
                )
            """), {"id": generation_id})

    result = _migrate(database_url, "head", check=False)
    assert result.returncode != 0
    assert "1 duplicate pending generation group" in result.stderr
    assert "pending-1" not in result.stderr and "pending-2" not in result.stderr
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM ai_generations WHERE status = 'pending'")) == 2
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PRE_ADMISSION_REVISION
    engine.dispose()
