from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone

from .model import Feature


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ALGORITHM_VERSION = "roadsense-vibration-v1"
BASELINE_METHOD = "window_magnitude_median"
QUALITY_FLAG_ORDER = (
    "source_time_gap",
    "source_time_non_monotonic",
    "incomplete_window",
    "invalid_sample",
)
FEATURE_FIELDS = {
    "schema_version", "run_id", "session_id", "sensor_id",
    "source_archive_sha256", "source_member", "window_index", "source_start",
    "source_end", "sample_count", "vibration_rms_mg", "peak_deviation_mg",
    "baseline_magnitude_mg", "baseline_method", "quality_flags", "algorithm_version",
}
EVENT_FIELDS = {
    "schema_version", "event_id", "event_type", "run_id", "session_id",
    "sensor_id", "source_archive_sha256", "source_member", "window_index",
    "source_start", "source_end", "algorithm_version", "heuristic_type",
    "rule_version", "severity", "threshold_vibration_rms_mg",
    "observed_vibration_rms_mg", "quality_flags",
}


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def parse_timestamp(value: object, field: str) -> tuple[str, datetime]:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be a UTC RFC 3339 string ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError(f"{field} must be valid RFC 3339") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return value, parsed


def _object_without_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def decode_object(encoded: bytes, description: str) -> dict[str, object]:
    try:
        payload = json.loads(encoded, object_pairs_hook=_object_without_duplicate_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{description} must be UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{description} must be an object")
    return payload


def _non_empty_string(payload: dict[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _non_negative_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _finite_non_negative(value: object, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return result


def parse_feature_message(encoded: bytes) -> Feature:
    payload = decode_object(encoded, "feature MQTT payload")
    if set(payload) != FEATURE_FIELDS:
        missing = sorted(FEATURE_FIELDS - set(payload))
        unknown = sorted(set(payload) - FEATURE_FIELDS)
        raise ValueError(f"feature fields mismatch; missing={missing}, unknown={unknown}")
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    run_id = _non_empty_string(payload, "run_id")
    try:
        parsed_run_id = uuid.UUID(run_id)
    except ValueError as error:
        raise ValueError("run_id must be a UUID") from error
    if str(parsed_run_id) != run_id:
        raise ValueError("run_id must use canonical lowercase UUID form")
    session_id = _non_empty_string(payload, "session_id")
    sensor_id = _non_empty_string(payload, "sensor_id")
    source_hash = _non_empty_string(payload, "source_archive_sha256")
    if not SHA256_PATTERN.fullmatch(source_hash):
        raise ValueError("source_archive_sha256 must be lowercase SHA-256")
    source_member = _non_empty_string(payload, "source_member")
    window_index = _non_negative_integer(payload.get("window_index"), "window_index")
    source_start_text, source_start = parse_timestamp(payload.get("source_start"), "source_start")
    source_end_text, source_end = parse_timestamp(payload.get("source_end"), "source_end")
    if (source_end - source_start).total_seconds() != 1:
        raise ValueError("feature window must be exactly one second")
    sample_count = _non_negative_integer(payload.get("sample_count"), "sample_count")
    if sample_count == 0:
        raise ValueError("sample_count must be positive")
    vibration_rms_mg = _finite_non_negative(payload.get("vibration_rms_mg"), "vibration_rms_mg")
    peak_deviation_mg = _finite_non_negative(payload.get("peak_deviation_mg"), "peak_deviation_mg")
    baseline_magnitude_mg = _finite_non_negative(payload.get("baseline_magnitude_mg"), "baseline_magnitude_mg")
    if payload.get("baseline_method") != BASELINE_METHOD:
        raise ValueError(f"baseline_method must be {BASELINE_METHOD}")
    flags = payload.get("quality_flags")
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        raise ValueError("quality_flags must be an array of strings")
    expected_flags = [flag for flag in QUALITY_FLAG_ORDER if flag in flags]
    if flags != expected_flags:
        raise ValueError("quality_flags must be known, unique, and in contract order")
    if payload.get("algorithm_version") != ALGORITHM_VERSION:
        raise ValueError(f"algorithm_version must be {ALGORITHM_VERSION}")
    return Feature(
        schema_version=1, run_id=run_id, session_id=session_id, sensor_id=sensor_id,
        source_archive_sha256=source_hash, source_member=source_member,
        window_index=window_index, source_start=source_start, source_end=source_end,
        source_start_text=source_start_text, source_end_text=source_end_text,
        sample_count=sample_count, vibration_rms_mg=vibration_rms_mg,
        peak_deviation_mg=peak_deviation_mg,
        baseline_magnitude_mg=baseline_magnitude_mg, baseline_method=BASELINE_METHOD,
        quality_flags=tuple(flags), algorithm_version=ALGORITHM_VERSION,
        payload_sha256=digest(payload), payload=payload,
    )


def validate_event_payload(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != EVENT_FIELDS:
        raise ValueError("event payload fields do not match the v1 contract")
    if payload.get("schema_version") != 1 or payload.get("event_type") != "high_vibration":
        raise ValueError("event schema_version/event_type is invalid")
    for field in (
        "event_id", "run_id", "session_id", "sensor_id", "source_archive_sha256",
        "source_member", "algorithm_version", "heuristic_type", "rule_version", "severity",
    ):
        _non_empty_string(payload, field)
    try:
        uuid.UUID(str(payload["event_id"]))
        uuid.UUID(str(payload["run_id"]))
    except ValueError as error:
        raise ValueError("event_id and run_id must be UUIDs") from error
    if not SHA256_PATTERN.fullmatch(str(payload["source_archive_sha256"])):
        raise ValueError("event source_archive_sha256 must be lowercase SHA-256")
    _non_negative_integer(payload.get("window_index"), "window_index")
    _, start = parse_timestamp(payload.get("source_start"), "source_start")
    _, end = parse_timestamp(payload.get("source_end"), "source_end")
    if (end - start).total_seconds() != 1:
        raise ValueError("event window must be exactly one second")
    _finite_non_negative(payload.get("threshold_vibration_rms_mg"), "threshold_vibration_rms_mg")
    _finite_non_negative(payload.get("observed_vibration_rms_mg"), "observed_vibration_rms_mg")
    flags = payload.get("quality_flags")
    if not isinstance(flags, list) or flags != [flag for flag in QUALITY_FLAG_ORDER if flag in flags]:
        raise ValueError("event quality_flags are invalid")
