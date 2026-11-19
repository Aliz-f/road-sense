from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterable

from .model import ImuSample
from .parser import parse_source_timestamp


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_SAMPLE_FIELDS = {
    "source_timestamp",
    "sample_index",
    "acc_x_mg",
    "acc_y_mg",
    "acc_z_mg",
}


def build_raw_payload(
    *,
    run_id: str,
    session_id: str,
    sensor_id: str,
    sequence_id: int,
    source_archive_sha256: str,
    source_member: str,
    samples: Iterable[ImuSample],
) -> dict[str, object]:
    payload = {
        "schema_version": 1,
        "run_id": run_id,
        "session_id": session_id,
        "sensor_id": sensor_id,
        "sequence_id": sequence_id,
        "source_archive_sha256": source_archive_sha256,
        "source_member": source_member,
        "acceleration_unit": "mg",
        "samples": [sample.as_payload() for sample in samples],
    }
    validate_raw_payload(payload)
    return payload


def encode_payload(payload: dict[str, object], max_payload_bytes: int) -> bytes:
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    if len(encoded) > max_payload_bytes:
        raise ValueError(
            f"encoded payload is {len(encoded)} bytes, limit is {max_payload_bytes}"
        )
    return encoded


def validate_raw_payload(payload: object) -> None:
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    try:
        uuid.UUID(str(payload.get("run_id")))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("run_id must be a UUID") from error
    for field in ("session_id", "sensor_id", "source_member"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise ValueError(f"{field} must be a non-empty string")
    sequence_id = payload.get("sequence_id")
    if not isinstance(sequence_id, int) or isinstance(sequence_id, bool) or sequence_id < 0:
        raise ValueError("sequence_id must be a non-negative integer")
    source_hash = payload.get("source_archive_sha256")
    if not isinstance(source_hash, str) or not SHA256_PATTERN.fullmatch(source_hash):
        raise ValueError("source_archive_sha256 must be lowercase SHA-256")
    if payload.get("acceleration_unit") != "mg":
        raise ValueError("acceleration_unit must be mg")
    samples = payload.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("samples must be a non-empty array")

    previous_index: int | None = None
    previous_time = None
    for sample in samples:
        if not isinstance(sample, dict) or not REQUIRED_SAMPLE_FIELDS.issubset(sample):
            raise ValueError("sample is missing required fields")
        index = sample["sample_index"]
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            raise ValueError("sample_index must be a non-negative integer")
        if previous_index is not None and index != previous_index + 1:
            raise ValueError("sample_index must be contiguous inside a batch")
        previous_index = index
        source_time = parse_source_timestamp(str(sample["source_timestamp"]))
        if previous_time is not None and source_time <= previous_time:
            raise ValueError("sample timestamps must be strictly increasing")
        previous_time = source_time
        for axis in ("acc_x_mg", "acc_y_mg", "acc_z_mg"):
            value = sample[axis]
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{axis} must be an integer")
