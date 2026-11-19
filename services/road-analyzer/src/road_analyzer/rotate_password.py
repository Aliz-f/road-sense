from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from .config import AnalyzerConfig
from .events import emit, emit_error


def atomic_secret_write(path: Path, value: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def rotate(config: AnalyzerConfig) -> None:
    current_path = config.postgres_password_file
    fallback_path = config.postgres_previous_password_file
    if current_path is None or fallback_path is None:
        raise ValueError("password rotation requires current and fallback password files")

    connection = None
    for password in config.postgres_password_candidates():
        try:
            connection = psycopg.connect(config.postgres_dsn(password), autocommit=False)
            break
        except psycopg.OperationalError:
            continue
    if connection is None:
        raise ConnectionError("none of the password files authenticates to PostgreSQL")

    new_password = secrets.token_hex(32)
    # Persist the future credential as a fallback before changing PostgreSQL.
    # At every interruption point either the current or fallback file works.
    atomic_secret_write(fallback_path, new_password)
    try:
        with connection:
            with connection.cursor() as cursor:
                # PostgreSQL does not accept a bind parameter in ALTER ROLE's
                # password grammar. psycopg's Literal still quotes/escapes it.
                cursor.execute(
                    sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                        sql.Identifier(config.postgres_user), sql.Literal(new_password)
                    )
                )
        with psycopg.connect(config.postgres_dsn(new_password)) as verification:
            with verification.cursor() as cursor:
                cursor.execute("SELECT current_user")
                if cursor.fetchone()[0] != config.postgres_user:
                    raise RuntimeError("rotated credential authenticated as an unexpected role")
        atomic_secret_write(current_path, new_password)
        fallback_path.unlink(missing_ok=True)
    finally:
        connection.close()


def main() -> int:
    if sys.argv[1:] != ["--apply"]:
        print("usage: python -m road_analyzer.rotate_password --apply", file=sys.stderr)
        return 2
    try:
        rotate(AnalyzerConfig.from_environment())
        emit("postgres_password_rotated")
        return 0
    except Exception as error:
        emit_error("postgres_password_rotation_failed", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
