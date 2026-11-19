from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from datetime import datetime, timezone

from .model import (
    InvalidRawSample,
    RawBatch,
    RawSample,
    RunCompletion,
    RunMetadata,
)


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
ALGORITHM_VERSION = "roadsense-vibration-v1"
BASELINE_METHOD = "window_magnitude_median"
QUALITY_FLAGS = {
    "source_time_gap",
    "source_time_non_monotonic",
    "incomplete_window",
    "invalid_sample",
}
QUALITY_FLAG_ORDER = (
    "source_time_gap",
    "source_time_non_monotonic",
    "incomplete_window",
    "invalid_sample",
)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def parse_source_timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("source_timestamp must be a UTC RFC 3339 string ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("source_timestamp must be valid RFC 3339") from error
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError("source_timestamp must be UTC")
    return parsed


def format_source_timestamp(value: datetime) -> str:
    timespec = "milliseconds" if value.microsecond % 1000 == 0 else "microseconds"
    return value.astimezone(timezone.utc).isoformat(timespec=timespec).replace(
        "+00:00", "Z"
    )


def _non_empty_string(payload: dict[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _non_negative_integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _decode_object(encoded: bytes, description: str) -> dict[str, object]:
    try:
        payload = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{description} must be UTF-8 JSON") from error
    if not isinstance(payload, dict):
        raise ValueError(f"{description} must be an object")
    return payload


def _parse_metadata(payload: dict[str, object]) -> RunMetadata:
    run_id = _non_empty_string(payload, "run_id")
    try:
        uuid.UUID(run_id)
    except ValueError as error:
        raise ValueError("run_id must be a UUID") from error
    metadata = RunMetadata(
        run_id=run_id,
        session_id=_non_empty_string(payload, "session_id"),
        sensor_id=_non_empty_string(payload, "sensor_id"),
        source_archive_sha256=_non_empty_string(payload, "source_archive_sha256"),
        source_member=_non_empty_string(payload, "source_member"),
    )
    if not SHA256_PATTERN.fullmatch(metadata.source_archive_sha256):
        raise ValueError("source_archive_sha256 must be lowercase SHA-256")
    return metadata


def parse_raw_message(encoded: bytes) -> RawBatch:
    payload = _decode_object(encoded, "raw MQTT payload")
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    metadata = _parse_metadata(payload)
    if payload.get("acceleration_unit") != "mg":
        raise ValueError("acceleration_unit must be mg")
    sequence_id = _non_negative_integer(payload.get("sequence_id"), "sequence_id")
    raw_samples = payload.get("samples")
    if not isinstance(raw_samples, list) or not raw_samples:
        raise ValueError("samples must be a non-empty array")

    samples: list[RawSample | InvalidRawSample] = []
    for raw_sample in raw_samples:
        try:
            if not isinstance(raw_sample, dict):
                raise ValueError("sample must be an object")
            sample_index = _non_negative_integer(
                raw_sample.get("sample_index"), "sample_index"
            )
            source_timestamp = _non_empty_string(raw_sample, "source_timestamp")
            source_time = parse_source_timestamp(source_timestamp)
            axes: list[int] = []
            for field in ("acc_x_mg", "acc_y_mg", "acc_z_mg"):
                value = raw_sample.get(field)
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValueError(f"{field} must be an integer")
                axes.append(value)
            samples.append(
                RawSample(
                    source_timestamp=source_timestamp,
                    source_time=source_time,
                    sample_index=sample_index,
                    acc_x_mg=axes[0],
                    acc_y_mg=axes[1],
                    acc_z_mg=axes[2],
                    digest=digest(raw_sample),
                )
            )
        except ValueError:
            # Preserve the record's source order so the processor applies its
            # invalid_sample flag at the correct point in a spanning batch.
            invalid_time = None
            invalid_index = None
            if isinstance(raw_sample, dict):
                try:
                    invalid_time = parse_source_timestamp(
                        raw_sample.get("source_timestamp")
                    )
                except ValueError:
                    pass
                candidate_index = raw_sample.get("sample_index")
                if (
                    isinstance(candidate_index, int)
                    and not isinstance(candidate_index, bool)
                    and candidate_index >= 0
                ):
                    invalid_index = candidate_index
            samples.append(
                InvalidRawSample(
                    source_time=invalid_time,
                    sample_index=invalid_index,
                )
            )

    return RawBatch(
        metadata=metadata,
        sequence_id=sequence_id,
        samples=tuple(samples),
        digest=digest(payload),
    )


def parse_run_complete_message(encoded: bytes) -> RunCompletion:
    payload = _decode_object(encoded, "run-complete MQTT payload")
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if payload.get("event") != "run_complete":
        raise ValueError("event must be run_complete")
    metadata = _parse_metadata(payload)
    raw_message_count = _non_negative_integer(
        payload.get("raw_message_count"), "raw_message_count"
    )
    sample_count = _non_negative_integer(payload.get("sample_count"), "sample_count")
    last_sequence_id = _non_negative_integer(
        payload.get("last_sequence_id"), "last_sequence_id"
    )
    last_sample_index = _non_negative_integer(
        payload.get("last_sample_index"), "last_sample_index"
    )
    if raw_message_count <= 0 or sample_count <= 0:
        raise ValueError("run-complete counts must be positive")
    if last_sequence_id != raw_message_count - 1:
        raise ValueError("last_sequence_id does not match raw_message_count")
    if last_sample_index != sample_count - 1:
        raise ValueError("last_sample_index does not match sample_count")
    return RunCompletion(
        metadata=metadata,
        raw_message_count=raw_message_count,
        sample_count=sample_count,
        last_sequence_id=last_sequence_id,
        last_sample_index=last_sample_index,
        digest=digest(payload),
    )


def validate_feature_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("feature payload must be an object")
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    try:
        uuid.UUID(str(payload.get("run_id")))
    except (TypeError, ValueError) as error:
        raise ValueError("run_id must be a UUID") from error
    for field in (
        "session_id",
        "sensor_id",
        "source_archive_sha256",
        "source_member",
    ):
        _non_empty_string(payload, field)
    if not SHA256_PATTERN.fullmatch(str(payload["source_archive_sha256"])):
        raise ValueError("source_archive_sha256 must be lowercase SHA-256")
    _non_negative_integer(payload.get("window_index"), "window_index")
    sample_count = _non_negative_integer(payload.get("sample_count"), "sample_count")
    if sample_count == 0:
        raise ValueError("sample_count must be positive")
    start = parse_source_timestamp(payload.get("source_start"))
    end = parse_source_timestamp(payload.get("source_end"))
    if (end - start).total_seconds() != 1:
        raise ValueError("feature window must be exactly one second")
    for field in (
        "vibration_rms_mg",
        "peak_deviation_mg",
        "baseline_magnitude_mg",
    ):
        value = payload.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{field} must be numeric")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{field} must be finite and non-negative")
    if payload.get("baseline_method") != BASELINE_METHOD:
        raise ValueError(f"baseline_method must be {BASELINE_METHOD}")
    if payload.get("algorithm_version") != ALGORITHM_VERSION:
        raise ValueError(f"algorithm_version must be {ALGORITHM_VERSION}")
    flags = payload.get("quality_flags")
    if not isinstance(flags, list) or any(flag not in QUALITY_FLAGS for flag in flags):
        raise ValueError("quality_flags contains an unknown value")
    if flags != [flag for flag in QUALITY_FLAG_ORDER if flag in flags]:
        raise ValueError("quality_flags must be unique and in contract order")
