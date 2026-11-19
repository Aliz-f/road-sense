from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RunMetadata:
    run_id: str
    session_id: str
    sensor_id: str
    source_archive_sha256: str
    source_member: str


@dataclass(frozen=True, slots=True)
class RawSample:
    source_timestamp: str
    source_time: datetime
    sample_index: int
    acc_x_mg: int
    acc_y_mg: int
    acc_z_mg: int
    digest: str


@dataclass(frozen=True, slots=True)
class InvalidRawSample:
    source_time: datetime | None
    sample_index: int | None


@dataclass(frozen=True, slots=True)
class RawBatch:
    metadata: RunMetadata
    sequence_id: int
    samples: tuple[RawSample | InvalidRawSample, ...]
    digest: str


@dataclass(frozen=True, slots=True)
class RunCompletion:
    metadata: RunMetadata
    raw_message_count: int
    sample_count: int
    last_sequence_id: int
    last_sample_index: int
    digest: str


@dataclass(slots=True)
class Window:
    window_index: int
    magnitudes_mg: list[float] = field(default_factory=list)
    quality_flags: set[str] = field(default_factory=set)
