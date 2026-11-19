from __future__ import annotations

import sys

import psycopg

from .config import AnalyzerConfig


def main() -> int:
    try:
        config = AnalyzerConfig.from_environment()
        if not config.ready_file.is_file():
            return 1
        with psycopg.connect(config.postgres_dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return 0
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
