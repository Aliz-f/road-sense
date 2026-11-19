from __future__ import annotations

import uuid

from .model import Feature


EVENT_NAMESPACE = uuid.UUID("dc9829cf-25c7-4d57-9189-c9e308999a5f")


def is_high_vibration(feature: Feature, threshold_mg: float) -> bool:
    return feature.vibration_rms_mg >= threshold_mg


def build_event(feature: Feature, threshold_mg: float, rule_version: str) -> dict[str, object]:
    identity = "|".join((feature.run_id, str(feature.window_index), feature.algorithm_version, rule_version))
    return {
        "schema_version": 1,
        "event_id": str(uuid.uuid5(EVENT_NAMESPACE, identity)),
        "event_type": "high_vibration",
        "run_id": feature.run_id,
        "session_id": feature.session_id,
        "sensor_id": feature.sensor_id,
        "source_archive_sha256": feature.source_archive_sha256,
        "source_member": feature.source_member,
        "window_index": feature.window_index,
        "source_start": feature.source_start_text,
        "source_end": feature.source_end_text,
        "algorithm_version": feature.algorithm_version,
        "heuristic_type": "vibration_rms_threshold",
        "rule_version": rule_version,
        "severity": "high",
        "threshold_vibration_rms_mg": threshold_mg,
        "observed_vibration_rms_mg": feature.vibration_rms_mg,
        "quality_flags": list(feature.quality_flags),
    }
