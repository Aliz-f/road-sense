from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Feature:
    schema_version: int
    run_id: str
    session_id: str
    sensor_id: str
    source_archive_sha256: str
    source_member: str
    window_index: int
    source_start: datetime
    source_end: datetime
    source_start_text: str
    source_end_text: str
    sample_count: int
    vibration_rms_mg: float
    peak_deviation_mg: float
    baseline_magnitude_mg: float
    baseline_method: str
    quality_flags: tuple[str, ...]
    algorithm_version: str
    payload_sha256: str
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class SessionRecord:
    session_id: str
    sensor_id: str
    source_archive_sha256: str
    source_member: str
    source_start: datetime
    source_end: datetime
    source_start_text: str
    source_end_text: str
    row_count: int
    road_category: str
    orientation_note: str


@dataclass(frozen=True, slots=True)
class StoreResult:
    duplicate: bool
    event_payload: dict[str, object] | None
