import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import MetaData, Table, create_engine, func, select

import pytest

from app.verify_ctrl01_previous_upgrade import (
    CTRL01_PREVIOUS_REVISION,
    PREVIOUS_USERS,
    seed_previous_users,
    verify_upgraded_users,
)
from app.verify_ctrl01_migration import SchemaContractError


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


def test_previous_to_head_preserves_users_and_does_not_grant_platform_access(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'previous-to-head.db'}"
    migrate(database_url, CTRL01_PREVIOUS_REVISION)
    engine = create_engine(database_url)
    with engine.begin() as connection:
        seed_previous_users(connection)
    engine.dispose()

    migrate(database_url, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        users = Table("users", MetaData(), autoload_with=connection)
        connection.execute(
            users.update()
            .where(users.c.id == PREVIOUS_USERS[0]["id"])
            .values(full_name="corrupted during upgrade")
        )
        with pytest.raises(SchemaContractError, match="full_name"):
            verify_upgraded_users(connection, cleanup=True)
        connection.execute(
            users.update()
            .where(users.c.id == PREVIOUS_USERS[0]["id"])
            .values(full_name=PREVIOUS_USERS[0]["full_name"])
        )
        verify_upgraded_users(connection, cleanup=True)
        assert connection.scalar(
            select(func.count()).select_from(users).where(users.c.id.in_([row["id"] for row in PREVIOUS_USERS]))
        ) == 0
        assert len(PREVIOUS_USERS) == 2
    engine.dispose()


def test_cli_refuses_disposable_sqlite_before_opening_it(tmp_path):
    database_path = tmp_path / "refused.db"
    environment = os.environ.copy()
    environment["MARKETPLACE_DATABASE_URL"] = f"sqlite:///{database_path}"
    result = subprocess.run(
        [sys.executable, "-m", "app.verify_ctrl01_previous_upgrade", "seed"],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stderr.strip().endswith("requires the ephemeral PostgreSQL CI database")
    assert not database_path.exists()
