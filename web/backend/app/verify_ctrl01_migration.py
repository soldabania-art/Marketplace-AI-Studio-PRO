"""Verify the migrated CTRL01 schema without loading ORM metadata."""

from pathlib import Path
import re
import sys

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import DateTime, JSON, String, inspect
from sqlalchemy.engine import Connection

from .db import engine


class SchemaContractError(RuntimeError):
    """The live database does not satisfy the CTRL01 migration contract."""


EXPECTED_COLUMNS = {
    "platform_bootstrap_states": {
        "key": (String, False, 80),
        "completed_at": (DateTime, False, None),
        "details": (JSON, False, None),
    },
    "platform_staff_roles": {
        "user_id": (String, False, 36),
        "role": (String, False, 15),
        "granted_by_user_id": (String, True, 36),
        "granted_at": (DateTime, False, None),
        "revoked_at": (DateTime, True, None),
        "revoked_by_user_id": (String, True, 36),
    },
}

EXPECTED_FOREIGN_KEYS = {
    (("user_id",), "users", ("id",), "CASCADE"),
    (("granted_by_user_id",), "users", ("id",), "RESTRICT"),
    (("revoked_by_user_id",), "users", ("id",), "RESTRICT"),
}

EXPECTED_INDEXES = {
    "ix_platform_staff_roles_role": ("role",),
    "ix_platform_staff_roles_granted_by_user_id": ("granted_by_user_id",),
    "ix_platform_staff_roles_revoked_at": ("revoked_at",),
    "ix_platform_staff_roles_revoked_by_user_id": ("revoked_by_user_id",),
}


def _normalized_sql(sql: str) -> str:
    normalized = re.sub(r"\s+", " ", sql).strip().lower()
    normalized = re.sub(r"::(?:character varying|text)(?:\[\])?", "", normalized)
    return re.sub(r"[\s\"()]", "", normalized)


def _has_expected_role_check(checks: list[dict]) -> bool:
    accepted = {
        "rolein'owner','project_manager'",
        "role=anyarray['owner','project_manager']",
    }
    return any(
        check.get("name") == "platform_staff_role_name"
        and _normalized_sql(check.get("sqltext") or "") in accepted
        for check in checks
    )


def verify_ctrl01_schema(connection: Connection) -> None:
    """Inspect existing tables only; never create or mutate schema objects."""
    inspector = inspect(connection)
    available_tables = set(inspector.get_table_names())
    missing_tables = sorted(set(EXPECTED_COLUMNS) - available_tables)
    if missing_tables:
        raise SchemaContractError(f"missing tables: {', '.join(missing_tables)}")

    problems: list[str] = []
    for table_name, expected_columns in EXPECTED_COLUMNS.items():
        actual_columns = {column["name"]: column for column in inspector.get_columns(table_name)}
        for column_name, (type_class, nullable, length) in expected_columns.items():
            column = actual_columns.get(column_name)
            if column is None:
                problems.append(f"{table_name}.{column_name} is missing")
                continue
            if not isinstance(column["type"], type_class):
                problems.append(f"{table_name}.{column_name} has an unexpected type")
            if bool(column["nullable"]) is not nullable:
                problems.append(f"{table_name}.{column_name} has unexpected nullability")
            if length is not None and getattr(column["type"], "length", None) != length:
                problems.append(f"{table_name}.{column_name} has an unexpected length")
            if (
                connection.dialect.name == "postgresql"
                and type_class is DateTime
                and getattr(column["type"], "timezone", False) is not True
            ):
                problems.append(f"{table_name}.{column_name} must retain timezone information")

    expected_primary_keys = {
        "platform_bootstrap_states": ("key",),
        "platform_staff_roles": ("user_id",),
    }
    for table_name, expected_columns in expected_primary_keys.items():
        actual = tuple(inspector.get_pk_constraint(table_name).get("constrained_columns") or ())
        if actual != expected_columns:
            problems.append(f"{table_name} has an unexpected primary key")

    actual_foreign_keys = set()
    for foreign_key in inspector.get_foreign_keys("platform_staff_roles"):
        ondelete = (foreign_key.get("options") or {}).get("ondelete", "").upper()
        actual_foreign_keys.add((
            tuple(foreign_key.get("constrained_columns") or ()),
            foreign_key.get("referred_table"),
            tuple(foreign_key.get("referred_columns") or ()),
            ondelete,
        ))
    if not EXPECTED_FOREIGN_KEYS <= actual_foreign_keys:
        problems.append("platform_staff_roles has missing or incorrect foreign keys")

    if not _has_expected_role_check(inspector.get_check_constraints("platform_staff_roles")):
        problems.append("platform_staff_roles has a missing or incorrect role check constraint")

    actual_indexes = {
        item["name"]: tuple(item.get("column_names") or ())
        for item in inspector.get_indexes("platform_staff_roles")
    }
    for index_name, expected_columns in EXPECTED_INDEXES.items():
        if actual_indexes.get(index_name) != expected_columns:
            problems.append(f"{index_name} is missing or has unexpected columns")

    if problems:
        raise SchemaContractError("; ".join(problems))


def verify_current_revision(connection: Connection) -> str:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    graph_heads = tuple(ScriptDirectory.from_config(config).get_heads())
    if len(graph_heads) != 1:
        raise SchemaContractError(f"migration graph has {len(graph_heads)} heads; expected exactly one")

    database_heads = tuple(MigrationContext.configure(connection).get_current_heads())
    if database_heads != graph_heads:
        raise SchemaContractError("database revision does not match the sole migration graph head")
    return graph_heads[0]


def main() -> int:
    if engine.dialect.name != "postgresql":
        raise SchemaContractError("CTRL01 migration verification requires PostgreSQL")
    with engine.connect() as connection:
        verify_ctrl01_schema(connection)
        revision = verify_current_revision(connection)
    print(f"CTRL01 PostgreSQL migration contract verified at {revision}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SchemaContractError as error:
        print(f"CTRL01 migration verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print("CTRL01 migration verification failed: database inspection was unavailable", file=sys.stderr)
        raise SystemExit(1)
