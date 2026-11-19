from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import TypeVar

import psycopg

from .config import AnalyzerConfig
from .heuristic import build_event, is_high_vibration
from .model import Feature, OutboxEvent, SessionRecord, StoreResult
from .schema import digest


class ConflictingDataError(ValueError):
    """An idempotency key was reused with different immutable content."""


T = TypeVar("T")


class AnalyzerStore:
    """Transactional storage with bounded reconnect/retry for transient failures."""

    def __init__(self, connection: psycopg.Connection, config: AnalyzerConfig) -> None:
        self.connection = connection
        self.config = config

    @classmethod
    def connect_with_retry(cls, config: AnalyzerConfig) -> "AnalyzerStore":
        return cls(cls._connect(config), config)

    @staticmethod
    def _connect(config: AnalyzerConfig) -> psycopg.Connection:
        last_error: Exception | None = None
        for attempt in range(1, config.postgres_connect_retries + 1):
            try:
                for password in config.postgres_password_candidates():
                    try:
                        return psycopg.connect(config.postgres_dsn(password), autocommit=False)
                    except psycopg.OperationalError as error:
                        last_error = error
            except ValueError as error:
                last_error = error
            if attempt < config.postgres_connect_retries:
                time.sleep(config.postgres_connect_retry_delay_seconds)
        raise ConnectionError("could not connect to PostgreSQL after configured retries") from last_error

    def _reconnect(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass
        self.connection = self._connect(self.config)

    def _operation(self, operation: Callable[[psycopg.Cursor], T]) -> T:
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                with self.connection.transaction():
                    with self.connection.cursor() as cursor:
                        return operation(cursor)
            except (psycopg.OperationalError, psycopg.InterfaceError) as error:
                last_error = error
                if attempt == 0:
                    self._reconnect()
        raise ConnectionError("PostgreSQL operation failed after reconnect") from last_error

    def close(self) -> None:
        try:
            self.connection.close()
        except Exception:
            pass

    def register_rule(self) -> None:
        expected = (
            "vibration_rms_threshold",
            "vibration_rms_gte",
            "high_vibration",
            "high",
            self.config.vibration_rms_threshold_mg,
        )

        def operation(cursor: psycopg.Cursor) -> None:
            cursor.execute(
                """
                INSERT INTO heuristic_rules (
                  rule_version, heuristic_type, comparison_algorithm,
                  event_type, severity, threshold_vibration_rms_mg
                ) VALUES (%s,%s,%s,%s,%s,%s)
                ON CONFLICT (rule_version) DO NOTHING
                """,
                (self.config.rule_version, *expected),
            )
            cursor.execute(
                """
                SELECT heuristic_type, comparison_algorithm, event_type, severity,
                       threshold_vibration_rms_mg
                FROM heuristic_rules WHERE rule_version=%s
                """,
                (self.config.rule_version,),
            )
            if cursor.fetchone() != expected:
                raise ConflictingDataError(
                    "rule_version is already bound to incompatible heuristic semantics or threshold"
                )

        self._operation(operation)

    def store_feature(self, feature: Feature, session: SessionRecord) -> StoreResult:
        event_payload = None
        if is_high_vibration(feature, self.config.vibration_rms_threshold_mg):
            event_payload = build_event(
                feature, self.config.vibration_rms_threshold_mg, self.config.rule_version
            )

        def operation(cursor: psycopg.Cursor) -> StoreResult:
            self._ensure_session(cursor, session)
            self._ensure_run(cursor, feature)
            feature_id, duplicate = self._insert_feature(cursor, feature)
            if event_payload is not None:
                self._insert_event_and_outbox(cursor, feature_id, feature, event_payload)
            else:
                cursor.execute(
                    """
                    SELECT 1 FROM events
                    WHERE run_id=%s AND window_index=%s AND algorithm_version=%s
                      AND rule_version=%s
                    """,
                    (feature.run_id, feature.window_index, feature.algorithm_version,
                     self.config.rule_version),
                )
                if cursor.fetchone() is not None:
                    raise ConflictingDataError(
                        "stored event conflicts with the configured threshold/rule version"
                    )
            return StoreResult(duplicate=duplicate, event_detected=event_payload is not None)

        return self._operation(operation)

    def fetch_pending_events(self, limit: int = 100) -> list[OutboxEvent]:
        def operation(cursor: psycopg.Cursor) -> list[OutboxEvent]:
            cursor.execute(
                """
                SELECT event_id::text, payload, publish_attempts
                FROM event_outbox
                WHERE published_at IS NULL
                ORDER BY created_at, event_id
                LIMIT %s
                """,
                (limit,),
            )
            return [OutboxEvent(row[0], row[1], row[2]) for row in cursor.fetchall()]

        return self._operation(operation)

    def mark_event_published(self, event_id: str) -> None:
        def operation(cursor: psycopg.Cursor) -> None:
            cursor.execute(
                """
                UPDATE event_outbox
                SET published_at=COALESCE(published_at, now()), last_attempt_at=now(),
                    publish_attempts=publish_attempts + 1, last_error=NULL
                WHERE event_id=%s
                """,
                (event_id,),
            )
            if cursor.rowcount != 1:
                raise ConflictingDataError("outbox event disappeared before publication marking")

        self._operation(operation)

    def record_event_publish_failure(self, event_id: str, error: Exception) -> None:
        message = f"{type(error).__name__}: {error}"[:1000]

        def operation(cursor: psycopg.Cursor) -> None:
            cursor.execute(
                """
                UPDATE event_outbox
                SET last_attempt_at=now(), publish_attempts=publish_attempts + 1,
                    last_error=%s
                WHERE event_id=%s AND published_at IS NULL
                """,
                (message, event_id),
            )

        self._operation(operation)

    @staticmethod
    def _ensure_session(cursor: psycopg.Cursor, session: SessionRecord) -> None:
        cursor.execute(
            """
            INSERT INTO sessions (
              session_id, sensor_id, source_archive_sha256, source_member,
              source_start, source_end, row_count, road_category, orientation_note
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (session_id) DO NOTHING
            """,
            (session.session_id, session.sensor_id, session.source_archive_sha256,
             session.source_member, session.source_start, session.source_end,
             session.row_count, session.road_category, session.orientation_note),
        )
        cursor.execute(
            """
            SELECT sensor_id, source_archive_sha256, source_member, source_start,
                   source_end, row_count, road_category, orientation_note
            FROM sessions WHERE session_id=%s
            """,
            (session.session_id,),
        )
        expected = (session.sensor_id, session.source_archive_sha256, session.source_member,
                    session.source_start, session.source_end, session.row_count,
                    session.road_category, session.orientation_note)
        if cursor.fetchone() != expected:
            raise ConflictingDataError("session_id conflicts with stored immutable provenance")

    @staticmethod
    def _ensure_run(cursor: psycopg.Cursor, feature: Feature) -> None:
        cursor.execute(
            """
            INSERT INTO runs (
              run_id, session_id, sensor_id, algorithm_version,
              source_start, source_end, status
            ) VALUES (%s,%s,%s,%s,%s,%s,'observed')
            ON CONFLICT (run_id) DO NOTHING
            """,
            (feature.run_id, feature.session_id, feature.sensor_id,
             feature.algorithm_version, feature.source_start, feature.source_end),
        )
        cursor.execute(
            "SELECT session_id, sensor_id, algorithm_version FROM runs WHERE run_id=%s",
            (feature.run_id,),
        )
        if cursor.fetchone() != (feature.session_id, feature.sensor_id, feature.algorithm_version):
            raise ConflictingDataError("run_id conflicts with stored run provenance")
        cursor.execute(
            """
            UPDATE runs SET source_start=LEAST(source_start,%s),
                            source_end=GREATEST(source_end,%s), updated_at=now()
            WHERE run_id=%s
            """,
            (feature.source_start, feature.source_end, feature.run_id),
        )

    @staticmethod
    def _insert_feature(cursor: psycopg.Cursor, feature: Feature) -> tuple[int, bool]:
        cursor.execute(
            """
            INSERT INTO feature_windows (
              run_id, window_index, algorithm_version, source_start, source_end,
              sample_count, vibration_rms_mg, peak_deviation_mg,
              baseline_magnitude_mg, baseline_method, quality_flags, payload_sha256
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (run_id, window_index, algorithm_version) DO NOTHING
            RETURNING feature_window_id
            """,
            (feature.run_id, feature.window_index, feature.algorithm_version,
             feature.source_start, feature.source_end, feature.sample_count,
             feature.vibration_rms_mg, feature.peak_deviation_mg,
             feature.baseline_magnitude_mg, feature.baseline_method,
             list(feature.quality_flags), feature.payload_sha256),
        )
        inserted = cursor.fetchone()
        if inserted is not None:
            return inserted[0], False
        cursor.execute(
            """
            SELECT feature_window_id, payload_sha256 FROM feature_windows
            WHERE run_id=%s AND window_index=%s AND algorithm_version=%s
            """,
            (feature.run_id, feature.window_index, feature.algorithm_version),
        )
        stored = cursor.fetchone()
        if stored is None or stored[1] != feature.payload_sha256:
            raise ConflictingDataError("feature idempotency key has conflicting content")
        return stored[0], True

    @staticmethod
    def _insert_event_and_outbox(cursor: psycopg.Cursor, feature_id: int,
                                 feature: Feature, event_payload: dict[str, object]) -> None:
        payload_sha256 = digest(event_payload)
        cursor.execute(
            """
            INSERT INTO events (
              event_id, feature_window_id, run_id, window_index, algorithm_version,
              event_type, heuristic_type, rule_version, severity,
              threshold_vibration_rms_mg, observed_vibration_rms_mg, payload_sha256
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (run_id, window_index, algorithm_version, rule_version) DO NOTHING
            RETURNING event_id
            """,
            (event_payload["event_id"], feature_id, feature.run_id, feature.window_index,
             feature.algorithm_version, event_payload["event_type"],
             event_payload["heuristic_type"], event_payload["rule_version"],
             event_payload["severity"], event_payload["threshold_vibration_rms_mg"],
             event_payload["observed_vibration_rms_mg"], payload_sha256),
        )
        if cursor.fetchone() is None:
            cursor.execute(
                """
                SELECT event_id::text, feature_window_id, payload_sha256 FROM events
                WHERE run_id=%s AND window_index=%s AND algorithm_version=%s
                  AND rule_version=%s
                """,
                (feature.run_id, feature.window_index, feature.algorithm_version,
                 event_payload["rule_version"]),
            )
            if cursor.fetchone() != (event_payload["event_id"], feature_id, payload_sha256):
                raise ConflictingDataError("event idempotency key has conflicting content")
        cursor.execute(
            """
            INSERT INTO event_outbox (event_id, payload)
            VALUES (%s,%s::jsonb)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (event_payload["event_id"], json.dumps(event_payload, separators=(",", ":"), sort_keys=True)),
        )
        cursor.execute("SELECT payload FROM event_outbox WHERE event_id=%s", (event_payload["event_id"],))
        row = cursor.fetchone()
        if row is None or row[0] != event_payload:
            raise ConflictingDataError("event outbox payload conflicts with stored event")
