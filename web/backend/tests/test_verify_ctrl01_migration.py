import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text

import pytest

from app.verify_ctrl01_migration import (
    SchemaContractError,
    _has_expected_role_check,
    verify_ctrl01_schema,
    verify_current_revision,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def migrate(database_url, revision):
    environment = os.environ.copy()
    environment["MARKETPLACE_DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        cwd=BACKEND_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_verifier_reports_missing_table_without_creating_orm_schema(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'incomplete-schema.db'}")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE platform_bootstrap_states (
                key VARCHAR(80) NOT NULL PRIMARY KEY,
                completed_at DATETIME NOT NULL,
                details JSON NOT NULL
            )
        """))
        before = set(inspect(connection).get_table_names())

        with pytest.raises(SchemaContractError, match="missing tables: platform_staff_roles"):
            verify_ctrl01_schema(connection)

        assert set(inspect(connection).get_table_names()) == before
        assert "platform_staff_roles" not in before
    engine.dispose()


def test_verifier_accepts_schema_produced_by_real_alembic_chain(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'migrated.db'}"
    migrate(database_url, "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        verify_ctrl01_schema(connection)
        assert verify_current_revision(connection) == "20260920_0033"
    engine.dispose()


def test_revision_verifier_rejects_database_behind_graph_head(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'previous.db'}"
    migrate(database_url, "20260913_ctrl01_staff")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        with pytest.raises(SchemaContractError, match="does not match"):
            verify_current_revision(connection)
    engine.dispose()


def test_cli_refuses_sqlite_without_exposing_database_url(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'must-not-run.db'}"
    environment = os.environ.copy()
    environment["MARKETPLACE_DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "app.verify_ctrl01_migration"],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stderr.strip().endswith("requires PostgreSQL")
    assert database_url not in result.stderr


@pytest.mark.parametrize("sqltext", [
    "role IN ('owner', 'project_manager', 'intruder')",
    "role IN ('owner', 'project_manager') OR true",
])
def test_role_check_rejects_broader_constraints(sqltext):
    assert not _has_expected_role_check([{"name": "platform_staff_role_name", "sqltext": sqltext}])


def test_role_check_accepts_postgresql_reflection_form():
    sqltext = (
        "((role)::text = ANY ((ARRAY['owner'::character varying, "
        "'project_manager'::character varying])::text[]))"
    )
    assert _has_expected_role_check([{"name": "platform_staff_role_name", "sqltext": sqltext}])
