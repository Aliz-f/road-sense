from __future__ import annotations

import json


def feature_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "run_id": "44444444-4444-4444-8444-444444444444",
        "session_id": "bumpy-gravel-20261019",
        "sensor_id": "bosch-xdk-110",
        "source_archive_sha256": "91d37ad4de7106d5038ed7bffe1e373db65e0f4771865da8975a216e76ed34f3",
        "source_member": "imu/bosch_imu.csv",
        "window_index": 0,
        "source_start": "2026-10-19T05:51:57.052Z",
        "source_end": "2026-10-19T05:51:58.052Z",
        "sample_count": 84,
        "vibration_rms_mg": 101.25,
        "peak_deviation_mg": 240.5,
        "baseline_magnitude_mg": 1042.0,
        "baseline_method": "window_magnitude_median",
        "quality_flags": [],
        "algorithm_version": "roadsense-vibration-v1",
    }
    payload.update(overrides)
    return payload


def encoded_feature(**overrides: object) -> bytes:
    return json.dumps(feature_payload(**overrides)).encode("utf-8")
