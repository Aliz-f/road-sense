from __future__ import annotations

import json
import unittest

from signal_processor.schema import (
    parse_raw_message,
    parse_run_complete_message,
    validate_feature_payload,
)


class SchemaTests(unittest.TestCase):
    def test_rejects_non_json_and_wrong_schema(self) -> None:
        with self.assertRaisesRegex(ValueError, "UTF-8 JSON"):
            parse_raw_message(b"not-json")
        with self.assertRaisesRegex(ValueError, "schema_version"):
            parse_raw_message(json.dumps({"schema_version": 2}).encode())

    def test_rejects_unknown_feature_flag(self) -> None:
        feature = {
            "schema_version": 1,
            "run_id": "97038d67-ca67-4202-b7b6-9439c1e64082",
            "session_id": "session",
            "sensor_id": "sensor",
            "source_archive_sha256": "a" * 64,
            "source_member": "imu.csv",
            "window_index": 0,
            "source_start": "2026-10-19T05:51:57.052Z",
            "source_end": "2026-10-19T05:51:58.052Z",
            "sample_count": 1,
            "vibration_rms_mg": 0.0,
            "peak_deviation_mg": 0.0,
            "baseline_magnitude_mg": 1000.0,
            "baseline_method": "window_magnitude_median",
            "quality_flags": ["unknown"],
            "algorithm_version": "roadsense-vibration-v1",
        }
        with self.assertRaisesRegex(ValueError, "unknown value"):
            validate_feature_payload(feature)

    def test_validates_run_complete_counts(self) -> None:
        completion = {
            "schema_version": 1,
            "event": "run_complete",
            "run_id": "97038d67-ca67-4202-b7b6-9439c1e64082",
            "session_id": "session",
            "sensor_id": "sensor",
            "source_archive_sha256": "a" * 64,
            "source_member": "imu.csv",
            "raw_message_count": 2,
            "sample_count": 10,
            "last_sequence_id": 1,
            "last_sample_index": 9,
        }
        parsed = parse_run_complete_message(json.dumps(completion).encode())
        self.assertEqual(parsed.raw_message_count, 2)
        completion["last_sequence_id"] = 4
        with self.assertRaisesRegex(ValueError, "last_sequence_id"):
            parse_run_complete_message(json.dumps(completion).encode())


if __name__ == "__main__":
    unittest.main()
