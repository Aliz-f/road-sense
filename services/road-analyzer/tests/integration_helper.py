from __future__ import annotations

import csv
import json
import math
import os
import ssl
import statistics
import sys
import tarfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import psycopg

from road_analyzer.config import AnalyzerConfig
from road_analyzer.registry import SessionRegistry
from road_analyzer.schema import digest, parse_feature_message
from road_analyzer.storage import AnalyzerStore


EXPECTED_EVENT_WINDOWS = [13, 14, 15, 16, 18]


def database_connection(config: AnalyzerConfig) -> psycopg.Connection:
    last_error = None
    for password in config.postgres_password_candidates():
        try:
            return psycopg.connect(config.postgres_dsn(password))
        except psycopg.OperationalError as error:
            last_error = error
    raise ConnectionError("integration helper could not authenticate to PostgreSQL") from last_error


def format_timestamp(value: datetime) -> str:
    value = value.astimezone(timezone.utc)
    timespec = "milliseconds" if value.microsecond % 1000 == 0 else "microseconds"
    return value.isoformat(timespec=timespec).replace("+00:00", "Z")


def reference_features(archive: Path, member: str, max_samples: int) -> list[dict[str, object]]:
    windows: dict[int, list[float]] = {}
    anchor = None
    with tarfile.open(archive) as tar:
        extracted = tar.extractfile(member)
        if extracted is None:
            raise ValueError(f"missing archive member: {member}")
        rows = csv.DictReader(line.decode("utf-8") for line in extracted)
        for sample_index, row in enumerate(rows):
            if sample_index >= max_samples:
                break
            source_time = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if anchor is None:
                anchor = source_time
            window_index = int((source_time - anchor).total_seconds())
            magnitude = math.sqrt(
                int(row["acc_x_mg"]) ** 2
                + int(row["acc_y_mg"]) ** 2
                + int(row["acc_z_mg"]) ** 2
            )
            windows.setdefault(window_index, []).append(magnitude)
    if anchor is None:
        raise ValueError("reference recording was empty")
    result = []
    last_index = max(windows)
    for window_index, magnitudes in sorted(windows.items()):
        baseline = statistics.median(magnitudes)
        deviations = [value - baseline for value in magnitudes]
        result.append(
            {
                "window_index": window_index,
                "source_start": format_timestamp(anchor + timedelta(seconds=window_index)),
                "source_end": format_timestamp(anchor + timedelta(seconds=window_index + 1)),
                "sample_count": len(magnitudes),
                "vibration_rms_mg": math.sqrt(
                    sum(value * value for value in deviations) / len(deviations)
                ),
                "peak_deviation_mg": max(abs(value) for value in deviations),
                "baseline_magnitude_mg": baseline,
                "quality_flags": ["incomplete_window"] if window_index == last_index else [],
            }
        )
    return result


def reference_payload(run_id: str, window_index: int = 13) -> dict[str, object]:
    archive = Path("/data/archives") / os.environ.get(
        "ROADSENSE_MVP_ARCHIVE", "Bumpy Gravel - imu.tar"
    )
    member = os.environ.get("ROADSENSE_MVP_MEMBER", "imu/bosch_imu.csv")
    feature = next(
        item for item in reference_features(archive, member, 1536)
        if item["window_index"] == window_index
    )
    return {
        "schema_version": 1,
        "run_id": run_id,
        "session_id": "bumpy-gravel-20261019",
        "sensor_id": "bosch-xdk-110",
        "source_archive_sha256": "91d37ad4de7106d5038ed7bffe1e373db65e0f4771865da8975a216e76ed34f3",
        "source_member": member,
        "window_index": feature["window_index"],
        "source_start": feature["source_start"],
        "source_end": feature["source_end"],
        "sample_count": feature["sample_count"],
        "vibration_rms_mg": feature["vibration_rms_mg"],
        "peak_deviation_mg": feature["peak_deviation_mg"],
        "baseline_magnitude_mg": feature["baseline_magnitude_mg"],
        "baseline_method": "window_magnitude_median",
        "quality_flags": feature["quality_flags"],
        "algorithm_version": "roadsense-vibration-v1",
    }


def verify(config: AnalyzerConfig, run_id: str) -> None:
    archive = Path("/data/archives") / os.environ.get(
        "ROADSENSE_MVP_ARCHIVE", "Bumpy Gravel - imu.tar"
    )
    member = os.environ.get("ROADSENSE_MVP_MEMBER", "imu/bosch_imu.csv")
    expected = reference_features(archive, member, 1536)
    with database_connection(config) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM schema_migrations")
            if cursor.fetchone()[0] != 5:
                raise AssertionError("expected exactly five applied migrations")
            cursor.execute(
                """
                SELECT e.payload_sha256, o.payload
                FROM events e JOIN event_outbox o USING (event_id)
                WHERE e.created_at < (
                  SELECT applied_at FROM schema_migrations
                  WHERE version='0002_phase04_reliability.sql'
                )
                """
            )
            for payload_sha256, payload in cursor.fetchall():
                if digest(payload) != payload_sha256:
                    raise AssertionError("legacy outbox payload is not canonical")
            cursor.execute(
                """
                SELECT heuristic_type, comparison_algorithm, event_type, severity,
                       threshold_vibration_rms_mg
                FROM heuristic_rules WHERE rule_version=%s
                """,
                (config.rule_version,),
            )
            if cursor.fetchone() != (
                "vibration_rms_threshold", "vibration_rms_gte", "high_vibration",
                "high", config.vibration_rms_threshold_mg,
            ):
                raise AssertionError("configured heuristic rule was not bound immutably")
            cursor.execute(
                """
                SELECT sensor_id, source_archive_sha256, source_member, row_count,
                       road_category, orientation_note
                FROM sessions WHERE session_id='bumpy-gravel-20261019'
                """
            )
            session = cursor.fetchone()
            if session != (
                "bosch-xdk-110",
                "91d37ad4de7106d5038ed7bffe1e373db65e0f4771865da8975a216e76ed34f3",
                "imu/bosch_imu.csv",
                62169,
                "Bumpy gravel",
                "Sensor orientation relative to the vehicle is unknown.",
            ):
                raise AssertionError(f"stored session provenance mismatch: {session}")
            cursor.execute(
                "SELECT session_id, sensor_id, algorithm_version, status FROM runs WHERE run_id=%s",
                (run_id,),
            )
            run = cursor.fetchone()
            if run != (
                "bumpy-gravel-20261019",
                "bosch-xdk-110",
                "roadsense-vibration-v1",
                "observed",
            ):
                raise AssertionError(f"stored run mismatch: {run}")
            cursor.execute(
                """
                SELECT window_index, sample_count, vibration_rms_mg,
                       peak_deviation_mg, baseline_magnitude_mg, quality_flags
                FROM feature_windows WHERE run_id=%s ORDER BY window_index
                """,
                (run_id,),
            )
            stored_features = cursor.fetchall()
            if len(stored_features) != len(expected):
                raise AssertionError(
                    f"expected {len(expected)} features, got {len(stored_features)}"
                )
            for stored, reference in zip(stored_features, expected, strict=True):
                if stored[0] != reference["window_index"] or stored[1] != reference["sample_count"]:
                    raise AssertionError(f"feature identity/count mismatch: {stored}")
                for actual, name in zip(stored[2:5], (
                    "vibration_rms_mg", "peak_deviation_mg", "baseline_magnitude_mg"
                ), strict=True):
                    if not math.isclose(actual, reference[name], rel_tol=1e-12, abs_tol=1e-12):
                        raise AssertionError(f"{name} mismatch for window {stored[0]}")
                if stored[5] != reference["quality_flags"]:
                    raise AssertionError(f"quality flags mismatch for window {stored[0]}")
            cursor.execute(
                "SELECT window_index FROM events WHERE run_id=%s ORDER BY window_index",
                (run_id,),
            )
            event_windows = [row[0] for row in cursor.fetchall()]
            if event_windows != EXPECTED_EVENT_WINDOWS:
                raise AssertionError(f"event windows mismatch: {event_windows}")
            cursor.execute(
                """
                SELECT count(*), count(*) FILTER (WHERE published_at IS NOT NULL)
                FROM event_outbox o JOIN events e USING (event_id)
                WHERE e.run_id=%s
                """,
                (run_id,),
            )
            if cursor.fetchone() != (len(EXPECTED_EVENT_WINDOWS), len(EXPECTED_EVENT_WINDOWS)):
                raise AssertionError("event outbox is incomplete or has pending rows")
    print(
        json.dumps(
            {
                "event": "phase04_database_verified",
                "run_id": run_id,
                "feature_count": len(expected),
                "event_count": len(EXPECTED_EVENT_WINDOWS),
                "event_windows": EXPECTED_EVENT_WINDOWS,
            },
            separators=(",", ":"), sort_keys=True,
        ),
        flush=True,
    )


def load_feature(config: AnalyzerConfig, run_id: str, window_index: int) -> dict[str, object]:
    with database_connection(config) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.session_id, r.sensor_id, s.source_archive_sha256, s.source_member,
                       f.window_index, f.source_start, f.source_end, f.sample_count,
                       f.vibration_rms_mg, f.peak_deviation_mg, f.baseline_magnitude_mg,
                       f.baseline_method, f.quality_flags, f.algorithm_version
                FROM feature_windows f
                JOIN runs r ON r.run_id=f.run_id
                JOIN sessions s ON s.session_id=r.session_id
                WHERE f.run_id=%s AND f.window_index=%s
                """,
                (run_id, window_index),
            )
            row = cursor.fetchone()
    if row is None:
        raise ValueError("stored feature not found")
    return {
        "schema_version": 1,
        "run_id": run_id,
        "session_id": row[0],
        "sensor_id": row[1],
        "source_archive_sha256": row[2],
        "source_member": row[3],
        "window_index": row[4],
        "source_start": format_timestamp(row[5]),
        "source_end": format_timestamp(row[6]),
        "sample_count": row[7],
        "vibration_rms_mg": row[8],
        "peak_deviation_mg": row[9],
        "baseline_magnitude_mg": row[10],
        "baseline_method": row[11],
        "quality_flags": row[12],
        "algorithm_version": row[13],
    }


def publish(config: AnalyzerConfig, payload: dict[str, object]) -> None:
    parse_feature_message(json.dumps(payload).encode())
    connected = threading.Event()
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"roadsense-phase04-helper-{os.getpid()}",
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(config.mqtt_username, config.mqtt_password)
    client.tls_set(ca_certs=str(config.mqtt_tls_ca_file), tls_version=ssl.PROTOCOL_TLS_CLIENT)

    def on_connect(client, userdata, flags, reason_code, properties) -> None:
        del client, userdata, flags, properties
        if reason_code == 0:
            connected.set()

    client.on_connect = on_connect
    client.connect(config.mqtt_host, config.mqtt_port, keepalive=30)
    client.loop_start()
    try:
        if not connected.wait(config.connect_timeout_seconds):
            raise TimeoutError("integration helper MQTT connection timed out")
        info = client.publish(
            config.feature_topic,
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(),
            qos=1,
        )
        info.wait_for_publish(config.publish_timeout_seconds)
        if not info.is_published():
            raise TimeoutError("integration helper feature publish timed out")
    finally:
        client.disconnect()
        client.loop_stop()


def store_direct(config: AnalyzerConfig, run_id: str) -> None:
    feature = parse_feature_message(json.dumps(reference_payload(run_id)).encode("utf-8"))
    registry = SessionRegistry.load(config.session_registry_file)
    store = AnalyzerStore.connect_with_retry(config)
    try:
        store.register_rule()
        result = store.store_feature(feature, registry.match(feature))
        if result.duplicate or not result.event_detected:
            raise AssertionError("direct outbox fixture was not a new detected event")
    finally:
        store.close()


def verify_single(config: AnalyzerConfig, run_id: str, published: bool = True) -> None:
    with database_connection(config) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM feature_windows WHERE run_id=%s", (run_id,))
            if cursor.fetchone()[0] != 1:
                raise AssertionError("expected one stored recovery feature")
            cursor.execute(
                """
                SELECT count(*), count(*) FILTER (WHERE o.published_at IS NOT NULL)
                FROM events e JOIN event_outbox o USING (event_id)
                WHERE e.run_id=%s
                """,
                (run_id,),
            )
            expected_published = 1 if published else 0
            if cursor.fetchone() != (1, expected_published):
                raise AssertionError("unexpected recovery event/outbox state")
    print(json.dumps({"event": "phase04_single_verified", "run_id": run_id,
                      "published": published}), flush=True)


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: integration_helper.py COMMAND RUN_ID", file=sys.stderr)
        return 2
    command, run_id = sys.argv[1:3]
    config = AnalyzerConfig.from_environment()
    if command == "verify":
        verify(config, run_id)
    elif command in {"duplicate", "conflict"}:
        payload = load_feature(config, run_id, 13)
        if command == "conflict":
            payload["vibration_rms_mg"] = float(payload["vibration_rms_mg"]) + 1.0
        publish(config, payload)
        print(json.dumps({"event": f"phase04_{command}_published", "run_id": run_id}), flush=True)
    elif command == "publish-reference":
        publish(config, reference_payload(run_id))
        print(json.dumps({"event": "phase04_reference_published", "run_id": run_id}), flush=True)
    elif command == "store-direct":
        store_direct(config, run_id)
        print(json.dumps({"event": "phase04_outbox_fixture_stored", "run_id": run_id}), flush=True)
    elif command == "verify-single":
        verify_single(config, run_id)
    elif command == "verify-single-pending":
        verify_single(config, run_id, published=False)
    else:
        raise ValueError(f"unknown integration helper command: {command}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
