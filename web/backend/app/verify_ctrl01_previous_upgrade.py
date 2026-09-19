"""Exercise CTRL01 previous-to-head data preservation without ORM imports."""

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, delete, func, inspect, select, text
from sqlalchemy.engine import Connection

from .db import engine
from .verify_ctrl01_migration import SchemaContractError, verify_ctrl01_schema, verify_current_revision


PREVIOUS_USERS = (
    {
        "id": "00000000-0000-4000-8000-000000000058",
        "email": "ctrl01-upgrade-active@example.invalid",
        "password_hash": "synthetic-active-hash",
        "full_name": "CTRL01 previous schema active marker",
        "is_active": True,
        "email_verified": True,
        "created_at": datetime(2026, 9, 12, 8, 15, tzinfo=timezone.utc),
    },
    {
        "id": "00000000-0000-4000-8000-000000000059",
        "email": "ctrl01-upgrade-disabled@example.invalid",
        "password_hash": "synthetic-disabled-hash",
        "full_name": "CTRL01 previous schema disabled marker",
        "is_active": False,
        "email_verified": False,
        "created_at": datetime(2026, 9, 11, 6, 45, tzinfo=timezone.utc),
    },
)

CTRL01_REVISION = "20260913_ctrl01_staff"
CTRL01_PREVIOUS_REVISION = "20260912_0028"


def _migration_revisions(connection: Connection) -> tuple[str, str, tuple[str, ...]]:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    script = ScriptDirectory.from_config(config)
    heads = tuple(script.get_heads())
    if len(heads) != 1:
        raise SchemaContractError(f"migration graph has {len(heads)} heads; expected exactly one")
    ctrl01 = script.get_revision(CTRL01_REVISION)
    if ctrl01 is None or ctrl01.down_revision != CTRL01_PREVIOUS_REVISION:
        raise SchemaContractError("CTRL01 does not have the expected reviewed predecessor")
    current = tuple(MigrationContext.configure(connection).get_current_heads())
    return heads[0], CTRL01_PREVIOUS_REVISION, current


def seed_previous_users(connection: Connection) -> None:
    _, previous, current = _migration_revisions(connection)
    if current != (previous,):
        raise SchemaContractError("database is not at the reviewed CTRL01 predecessor")
    if {"platform_staff_roles", "platform_bootstrap_states"} & set(inspect(connection).get_table_names()):
        raise SchemaContractError("CTRL01 tables already exist before the tested upgrade")
    users = Table("users", MetaData(), autoload_with=connection)
    fixture_ids = [row["id"] for row in PREVIOUS_USERS]
    if connection.scalar(select(func.count()).select_from(users).where(users.c.id.in_(fixture_ids))):
        raise SchemaContractError("synthetic previous-schema users already exist")
    connection.execute(users.insert(), PREVIOUS_USERS)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def verify_upgraded_users(connection: Connection, *, cleanup: bool) -> None:
    verify_ctrl01_schema(connection)
    verify_current_revision(connection)
    users = Table("users", MetaData(), autoload_with=connection)
    for expected in PREVIOUS_USERS:
        actual = connection.execute(select(users).where(users.c.id == expected["id"])).mappings().one_or_none()
        if actual is None:
            raise SchemaContractError("a synthetic previous-schema user was not preserved")
        for column in ("email", "password_hash", "full_name", "is_active", "email_verified"):
            if actual[column] != expected[column]:
                raise SchemaContractError(f"previous-schema user field was not preserved: {column}")
        if _utc(actual["created_at"]) != expected["created_at"]:
            raise SchemaContractError("previous-schema user field was not preserved: created_at")

    metadata = MetaData()
    roles = Table("platform_staff_roles", metadata, autoload_with=connection)
    bootstrap = Table("platform_bootstrap_states", metadata, autoload_with=connection)
    if connection.scalar(select(func.count()).select_from(roles)) != 0:
        raise SchemaContractError("CTRL01 migration implicitly granted a platform role")
    if connection.scalar(select(func.count()).select_from(bootstrap)) != 0:
        raise SchemaContractError("CTRL01 migration implicitly completed bootstrap")
    if cleanup:
        connection.execute(delete(users).where(users.c.id.in_([row["id"] for row in PREVIOUS_USERS])))


def _require_ephemeral_ci_database(connection: Connection) -> None:
    if connection.dialect.name != "postgresql" or os.getenv("CI") != "true":
        raise SchemaContractError("previous-upgrade verification requires the ephemeral PostgreSQL CI database")
    if connection.scalar(text("SELECT current_database()")) != "trovendi_ci":
        raise SchemaContractError("previous-upgrade verification requires the named ephemeral CI database")


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed")
    commands.add_parser("verify")
    args = parser.parse_args()
    if (
        engine.dialect.name != "postgresql"
        or os.getenv("CI") != "true"
        or engine.url.host not in {"localhost", "127.0.0.1"}
        or engine.url.database != "trovendi_ci"
    ):
        raise SchemaContractError("previous-upgrade verification requires the ephemeral PostgreSQL CI database")
    with engine.begin() as connection:
        _require_ephemeral_ci_database(connection)
        if args.command == "seed":
            seed_previous_users(connection)
        else:
            verify_upgraded_users(connection, cleanup=True)
    print(f"CTRL01 previous-upgrade {args.command} verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SchemaContractError as error:
        print(f"CTRL01 previous-upgrade verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("CTRL01 previous-upgrade verification failed: database inspection was unavailable", file=sys.stderr)
        raise SystemExit(1)
