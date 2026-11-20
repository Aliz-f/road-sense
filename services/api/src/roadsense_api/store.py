from __future__ import annotations

from collections.abc import Sequence
from contextlib import contextmanager
from typing import Any, Iterator
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .config import ApiConfig


class ApiStore:
    def __init__(self, config: ApiConfig) -> None:
        self.config = config

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        connection = None
        last_error: psycopg.OperationalError | None = None
        for password in self.config.password_candidates():
            try:
                connection = psycopg.connect(
                    **self.config.connection_kwargs(password), row_factory=dict_row
                )
                break
            except psycopg.OperationalError as error:
                last_error = error
        if connection is None:
            raise psycopg.OperationalError(
                "none of the configured PostgreSQL password files authenticated"
            ) from last_error
        with connection:
            connection.execute("SET TRANSACTION READ ONLY")
            yield connection

    def ready(self) -> None:
        with self.connection() as connection:
            connection.execute("SELECT 1").fetchone()

    def page(
        self, query: str, count_query: str, parameters: Sequence[Any], limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        with self.connection() as connection:
            total = connection.execute(count_query, parameters).fetchone()["total"]
            items = connection.execute(query, (*parameters, limit, offset)).fetchall()
        return items, total

    def sessions(self, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        return self.page(
            """
            SELECT s.session_id, s.sensor_id, s.source_archive_sha256, s.source_member,
                   s.source_start, s.source_end, s.row_count, s.road_category,
                   s.orientation_note, count(r.run_id)::integer AS run_count
            FROM sessions s LEFT JOIN runs r ON r.session_id=s.session_id
            GROUP BY s.session_id ORDER BY s.source_start, s.session_id LIMIT %s OFFSET %s
            """,
            "SELECT count(*)::integer AS total FROM sessions",
            (), limit, offset,
        )

    def runs(
        self, session_id: str | None, limit: int, offset: int
    ) -> tuple[list[dict[str, Any]], int]:
        where = "WHERE r.session_id=%s" if session_id is not None else ""
        params: tuple[Any, ...] = (session_id,) if session_id is not None else ()
        return self.page(
            f"""
            SELECT r.run_id, r.session_id, r.sensor_id, r.algorithm_version,
                   r.replay_rate, r.source_start, r.source_end, r.status,
                   (SELECT count(*)::integer FROM feature_windows f
                    WHERE f.run_id=r.run_id) AS feature_count,
                   (SELECT count(*)::integer FROM events e
                    WHERE e.run_id=r.run_id) AS event_count,
                   r.created_at, r.updated_at
            FROM runs r
            {where}
            ORDER BY r.created_at DESC, r.run_id LIMIT %s OFFSET %s
            """,
            f"SELECT count(*)::integer AS total FROM runs r {where}",
            params, limit, offset,
        )

    def run_exists(self, run_id: UUID) -> bool:
        with self.connection() as connection:
            return connection.execute(
                "SELECT EXISTS (SELECT 1 FROM runs WHERE run_id=%s) AS present", (run_id,)
            ).fetchone()["present"]

    def features(self, run_id: UUID, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        return self.page(
            """
            SELECT run_id, window_index, algorithm_version, source_start, source_end,
                   sample_count, vibration_rms_mg, peak_deviation_mg,
                   baseline_magnitude_mg, baseline_method, quality_flags
            FROM feature_windows WHERE run_id=%s
            ORDER BY window_index, algorithm_version LIMIT %s OFFSET %s
            """,
            "SELECT count(*)::integer AS total FROM feature_windows WHERE run_id=%s",
            (run_id,), limit, offset,
        )

    def events(self, run_id: UUID, limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
        return self.page(
            """
            SELECT e.event_id, e.run_id, e.window_index, e.algorithm_version,
                   f.source_start, f.source_end, e.event_type, e.heuristic_type,
                   e.rule_version, e.severity, e.threshold_vibration_rms_mg,
                   e.observed_vibration_rms_mg, f.quality_flags, e.created_at
            FROM events e JOIN feature_windows f ON f.feature_window_id=e.feature_window_id
            WHERE e.run_id=%s ORDER BY e.window_index, e.rule_version LIMIT %s OFFSET %s
            """,
            "SELECT count(*)::integer AS total FROM events WHERE run_id=%s",
            (run_id,), limit, offset,
        )

    def status(self) -> dict[str, Any]:
        with self.connection() as connection:
            return connection.execute(
                """
                SELECT (SELECT count(*) FROM sessions)::integer AS session_count,
                       (SELECT count(*) FROM runs)::integer AS run_count,
                       (SELECT count(*) FROM feature_windows)::integer AS feature_count,
                       (SELECT count(*) FROM events)::integer AS event_count,
                       (SELECT count(*) FROM event_outbox WHERE published_at IS NULL)::integer
                         AS pending_event_publications,
                       (SELECT max(created_at) FROM feature_windows) AS latest_feature_at
                """
            ).fetchone()
