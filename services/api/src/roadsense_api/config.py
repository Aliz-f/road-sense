from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApiConfig:
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password_file: Path
    postgres_previous_password_file: Path | None
    connect_timeout_seconds: int

    @classmethod
    def from_env(cls) -> "ApiConfig":
        port = int(os.environ.get("POSTGRES_PORT", "5432"))
        timeout = int(os.environ.get("POSTGRES_CONNECT_TIMEOUT_SECONDS", "5"))
        if not 1 <= port <= 65535:
            raise ValueError("POSTGRES_PORT must be between 1 and 65535")
        if timeout < 1:
            raise ValueError("POSTGRES_CONNECT_TIMEOUT_SECONDS must be positive")
        return cls(
            postgres_host=os.environ.get("POSTGRES_HOST", "postgres"),
            postgres_port=port,
            postgres_db=os.environ.get("POSTGRES_DB", "roadsense"),
            postgres_user=os.environ.get("POSTGRES_USER", "roadsense"),
            postgres_password_file=Path(
                os.environ.get("POSTGRES_PASSWORD_FILE", "/run/roadsense/postgres/password")
            ),
            postgres_previous_password_file=Path(
                os.environ.get(
                    "POSTGRES_PREVIOUS_PASSWORD_FILE",
                    "/run/roadsense/postgres/password.previous",
                )
            ),
            connect_timeout_seconds=timeout,
        )

    def password_candidates(self) -> tuple[str, ...]:
        candidates = [self._read_password_file(self.postgres_password_file)]
        previous = self.postgres_previous_password_file
        if previous is not None and previous.is_file():
            previous_password = self._read_password_file(previous)
            if previous_password not in candidates:
                candidates.append(previous_password)
        return tuple(candidates)

    @staticmethod
    def _read_password_file(path: Path) -> str:
        try:
            password = path.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as error:
            raise ValueError(f"cannot read PostgreSQL password file: {path}") from error
        if not password or "\n" in password or "\r" in password:
            raise ValueError(
                f"PostgreSQL password file must contain one non-empty line: {path}"
            )
        return password

    def connection_kwargs(self, password: str) -> dict[str, object]:
        return {
            "host": self.postgres_host,
            "port": self.postgres_port,
            "dbname": self.postgres_db,
            "user": self.postgres_user,
            "password": password,
            "connect_timeout": self.connect_timeout_seconds,
            "application_name": "roadsense-api",
        }
