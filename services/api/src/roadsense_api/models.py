from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(StrictModel):
    status: Literal["live", "ready"]


class SessionResponse(StrictModel):
    session_id: str
    sensor_id: str
    source_archive_sha256: str
    source_member: str
    source_start: datetime
    source_end: datetime
    row_count: int = Field(gt=0)
    road_category: str
    orientation_note: str
    run_count: int = Field(ge=0)


class RunResponse(StrictModel):
    run_id: UUID
    session_id: str
    sensor_id: str
    algorithm_version: str
    replay_rate: float | None
    source_start: datetime
    source_end: datetime
    status: Literal["observed"]
    feature_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class FeatureResponse(StrictModel):
    run_id: UUID
    window_index: int = Field(ge=0)
    algorithm_version: str
    source_start: datetime
    source_end: datetime
    sample_count: int = Field(gt=0)
    vibration_rms_mg: float = Field(ge=0)
    peak_deviation_mg: float = Field(ge=0)
    baseline_magnitude_mg: float = Field(ge=0)
    baseline_method: Literal["window_magnitude_median"]
    quality_flags: list[str]


class EventResponse(StrictModel):
    event_id: UUID
    run_id: UUID
    window_index: int = Field(ge=0)
    algorithm_version: str
    source_start: datetime
    source_end: datetime
    event_type: Literal["high_vibration"]
    heuristic_type: Literal["vibration_rms_threshold"]
    rule_version: str
    severity: Literal["high"]
    threshold_vibration_rms_mg: float = Field(gt=0)
    observed_vibration_rms_mg: float = Field(ge=0)
    quality_flags: list[str]
    created_at: datetime


class StatusResponse(StrictModel):
    session_count: int = Field(ge=0)
    run_count: int = Field(ge=0)
    feature_count: int = Field(ge=0)
    event_count: int = Field(ge=0)
    pending_event_publications: int = Field(ge=0)
    latest_feature_at: datetime | None


T = TypeVar("T")


class Page(StrictModel, Generic[T]):
    items: list[T]
    limit: int = Field(ge=1, le=500)
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    total: int = Field(ge=0)
