from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import psycopg

from .config import AnalyzerConfig
from .events import emit, emit_error


MIGRATION_LOCK_ID = 764_004


def apply_migrations(config: AnalyzerConfig, directory: Path = Path("/app/migrations")) -> None:
    migrations = sorted(directory.glob("*.sql"))
    if not migrations:
        raise ValueError(f"no SQL migrations found in {directory}")
    from .storage import AnalyzerStore

    store = AnalyzerStore.connect_with_retry(config)
    try:
        with store.connection.transaction():
            with store.connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK_ID,))
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                      version text PRIMARY KEY,
                      checksum character(64) NOT NULL,
                      applied_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                for path in migrations:
                    sql = path.read_text(encoding="utf-8")
                    checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
                    cursor.execute(
                        "SELECT checksum FROM schema_migrations WHERE version=%s",
                        (path.name,),
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        if row[0] != checksum:
                            raise ValueError(f"applied migration checksum changed: {path.name}")
                        emit("migration_already_applied", version=path.name)
                        continue
                    cursor.execute(sql)
                    cursor.execute(
                        "INSERT INTO schema_migrations (version, checksum) VALUES (%s,%s)",
                        (path.name, checksum),
                    )
                    emit("migration_applied", version=path.name)
    finally:
        store.close()


def main() -> int:
    try:
        apply_migrations(AnalyzerConfig.from_environment())
        emit("migrations_complete")
        return 0
    except Exception as error:
        emit_error("migration_failed", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
