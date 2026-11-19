from __future__ import annotations

import time

import psycopg

from .config import AnalyzerConfig
from .heuristic import build_event, is_high_vibration
from .model import Feature, SessionRecord, StoreResult
from .schema import digest


class ConflictingDataError(ValueError):
    """An idempotency key was reused with different immutable content."""


class AnalyzerStore:
    def __init__(self, connection: psycopg.Connection, config: AnalyzerConfig) -> None:
        self.connection = connection
        self.config = config

    @classmethod
    def connect_with_retry(cls, config: AnalyzerConfig) -> "AnalyzerStore":
        last_error: Exception | None = None
        for attempt in range(1, config.postgres_connect_retries + 1):
            try:
                connection = psycopg.connect(config.postgres_dsn, autocommit=False)
                return cls(connection, config)
            except psycopg.OperationalError as error:
                last_error = error
                if attempt < config.postgres_connect_retries:
                    time.sleep(1)
        raise ConnectionError("could not connect to PostgreSQL after configured retries") from last_error

    def close(self) -> None:
        self.connection.close()

    def store_feature(self, feature: Feature, session: SessionRecord) -> StoreResult:
        event_payload = None
        if is_high_vibration(feature, self.config.vibration_rms_threshold_mg):
            event_payload = build_event(
                feature, self.config.vibration_rms_threshold_mg, self.config.rule_version
            )
        with self.connection.transaction():
            with self.connection.cursor() as cursor:
                self._ensure_session(cursor, session)
                self._ensure_run(cursor, feature)
                feature_id, duplicate = self._insert_feature(cursor, feature)
                if event_payload is not None:
                    self._insert_event(cursor, feature_id, feature, event_payload)
                else:
                    cursor.execute(
                        """
                        SELECT 1 FROM events
                        WHERE run_id=%s AND window_index=%s AND algorithm_version=%s
                          AND rule_version=%s
                        """,
                        (feature.run_id, feature.window_index, feature.algorithm_version, self.config.rule_version),
                    )
                    if cursor.fetchone() is not None:
                        raise ConflictingDataError(
                            "stored event conflicts with the configured threshold/rule version"
                        )
        return StoreResult(duplicate=duplicate, event_payload=event_payload)

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
            (
                session.session_id, session.sensor_id, session.source_archive_sha256,
                session.source_member, session.source_start, session.source_end,
                session.row_count, session.road_category, session.orientation_note,
            ),
        )
        cursor.execute(
            """
            SELECT sensor_id, source_archive_sha256, source_member, source_start,
                   source_end, row_count, road_category, orientation_note
            FROM sessions WHERE session_id=%s
            """,
            (session.session_id,),
        )
        stored = cursor.fetchone()
        expected = (
            session.sensor_id, session.source_archive_sha256, session.source_member,
            session.source_start, session.source_end, session.row_count,
            session.road_category, session.orientation_note,
        )
        if stored != expected:
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
            (
                feature.run_id, feature.session_id, feature.sensor_id,
                feature.algorithm_version, feature.source_start, feature.source_end,
            ),
        )
        cursor.execute(
            "SELECT session_id, sensor_id, algorithm_version FROM runs WHERE run_id=%s",
            (feature.run_id,),
        )
        stored = cursor.fetchone()
        if stored != (feature.session_id, feature.sensor_id, feature.algorithm_version):
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
            (
                feature.run_id, feature.window_index, feature.algorithm_version,
                feature.source_start, feature.source_end, feature.sample_count,
                feature.vibration_rms_mg, feature.peak_deviation_mg,
                feature.baseline_magnitude_mg, feature.baseline_method,
                list(feature.quality_flags), feature.payload_sha256,
            ),
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
    def _insert_event(
        cursor: psycopg.Cursor,
        feature_id: int,
        feature: Feature,
        event_payload: dict[str, object],
    ) -> None:
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
            (
                event_payload["event_id"], feature_id, feature.run_id,
                feature.window_index, feature.algorithm_version,
                event_payload["event_type"], event_payload["heuristic_type"],
                event_payload["rule_version"], event_payload["severity"],
                event_payload["threshold_vibration_rms_mg"],
                event_payload["observed_vibration_rms_mg"], payload_sha256,
            ),
        )
        if cursor.fetchone() is not None:
            return
        cursor.execute(
            """
            SELECT event_id::text, feature_window_id, payload_sha256 FROM events
            WHERE run_id=%s AND window_index=%s AND algorithm_version=%s AND rule_version=%s
            """,
            (feature.run_id, feature.window_index, feature.algorithm_version, event_payload["rule_version"]),
        )
        stored = cursor.fetchone()
        if stored != (event_payload["event_id"], feature_id, payload_sha256):
            raise ConflictingDataError("event idempotency key has conflicting content")
