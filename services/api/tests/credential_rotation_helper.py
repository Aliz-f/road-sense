from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from roadsense_api.config import ApiConfig


def atomic_write(path: Path, value: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def connects(config: ApiConfig, password: str) -> bool:
    try:
        with psycopg.connect(**config.connection_kwargs(password)) as connection:
            return connection.execute("SELECT current_user").fetchone()[0] == config.postgres_user
    except psycopg.OperationalError:
        return False


def stage_interrupted_rotation(config: ApiConfig) -> None:
    previous = config.postgres_previous_password_file
    if previous is None:
        raise ValueError("fallback password path is required")
    if previous.exists():
        raise RuntimeError("refusing to overwrite an existing fallback password")
    current_password = config.password_candidates()[0]
    future_password = secrets.token_hex(32)
    atomic_write(previous, future_password)
    with psycopg.connect(**config.connection_kwargs(current_password)) as connection:
        connection.execute(
            sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(config.postgres_user), sql.Literal(future_password)
            )
        )
    print("Phase 05 interrupted credential rotation staged after database change: PASS")


def recover_rotation(config: ApiConfig) -> None:
    previous = config.postgres_previous_password_file
    if previous is None or not previous.is_file():
        return
    current_password = config._read_password_file(config.postgres_password_file)
    future_password = config._read_password_file(previous)
    if connects(config, future_password):
        atomic_write(config.postgres_password_file, future_password)
        previous.unlink()
    elif connects(config, current_password):
        previous.unlink()
    else:
        raise RuntimeError("neither staged credential authenticates; refusing data loss")
    print("Phase 05 credential rotation fixture recovered: PASS")


def main() -> int:
    if sys.argv[1:] == ["stage"]:
        stage_interrupted_rotation(ApiConfig.from_env())
        return 0
    if sys.argv[1:] == ["recover"]:
        recover_rotation(ApiConfig.from_env())
        return 0
    print("usage: credential_rotation_helper.py stage|recover", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
