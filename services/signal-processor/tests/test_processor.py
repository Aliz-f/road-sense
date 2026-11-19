from __future__ import annotations

import json
import math
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from signal_processor.processor import SignalEngine


BASE = datetime(2026, 10, 19, 5, 51, 57, 52_000, tzinfo=timezone.utc)
SOURCE_HASH = "91d37ad4de7106d5038ed7bffe1e373db65e0f4771865da8975a216e76ed34f3"


def timestamp(offset_seconds: float) -> str:
    value = BASE + timedelta(seconds=offset_seconds)
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sample(index: int, offset: float, magnitude: int = 1000) -> dict[str, object]:
    return {
        "source_timestamp": timestamp(offset),
        "sample_index": index,
        "acc_x_mg": magnitude,
        "acc_y_mg": 0,
        "acc_z_mg": 0,
    }


def payload(
    samples: list[object],
    *,
    run_id: str,
    sequence_id: int = 0,
    session_id: str = "bumpy-gravel-20261019",
    acceleration_unit: str = "mg",
) -> bytes:
    return json.dumps(
        {
            "schema_version": 1,
            "run_id": run_id,
            "session_id": session_id,
            "sensor_id": "bosch-xdk-110",
            "sequence_id": sequence_id,
            "source_archive_sha256": SOURCE_HASH,
            "source_member": "imu/bosch_imu.csv",
            "acceleration_unit": acceleration_unit,
            "samples": samples,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


class ProcessorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = str(uuid.uuid4())
        self.engine = SignalEngine()

    def test_hand_verified_median_rms_and_peak(self) -> None:
        self.engine.process_message(
            payload(
                [sample(0, 0.000, 990), sample(1, 0.012, 1000), sample(2, 0.024, 1010)],
                run_id=self.run_id,
            )
        )
        feature = self.engine.finalize_all()[0]

        self.assertEqual(feature["baseline_magnitude_mg"], 1000.0)
        self.assertAlmostEqual(feature["vibration_rms_mg"], math.sqrt(200 / 3), places=12)
        self.assertEqual(feature["peak_deviation_mg"], 10.0)
        self.assertEqual(feature["sample_count"], 3)
        self.assertEqual(feature["quality_flags"], ["incomplete_window"])

    def test_magnitude_is_orientation_robust(self) -> None:
        self.engine.process_message(
            payload(
                [
                    sample(0, 0.000, 1000),
                    {
                        **sample(1, 0.012, 0),
                        "acc_x_mg": 0,
                        "acc_y_mg": 600,
                        "acc_z_mg": 800,
                    },
                ],
                run_id=self.run_id,
            )
        )
        feature = self.engine.finalize_all()[0]
        self.assertEqual(feature["baseline_magnitude_mg"], 1000.0)
        self.assertEqual(feature["vibration_rms_mg"], 0.0)
        self.assertEqual(feature["peak_deviation_mg"], 0.0)

    def test_windows_are_half_open_and_source_time_anchored(self) -> None:
        features = self.engine.process_message(
            payload(
                [sample(0, 0.000), sample(1, 0.999), sample(2, 1.000)],
                run_id=self.run_id,
            )
        )
        self.assertEqual(len(features), 1)
        self.assertEqual(features[0]["window_index"], 0)
        self.assertEqual(features[0]["sample_count"], 2)
        self.assertEqual(features[0]["source_start"], timestamp(0))
        self.assertEqual(features[0]["source_end"], timestamp(1))

    def test_gap_threshold_is_strictly_greater_than_18_ms(self) -> None:
        self.engine.process_message(
            payload(
                [sample(0, 0.000), sample(1, 0.018), sample(2, 0.037)],
                run_id=self.run_id,
            )
        )
        feature = self.engine.finalize_all()[0]
        self.assertEqual(
            feature["quality_flags"], ["source_time_gap", "incomplete_window"]
        )

    def test_missing_sample_index_is_flagged_without_interpolation(self) -> None:
        self.engine.process_message(
            payload([sample(0, 0.000), sample(2, 0.012)], run_id=self.run_id)
        )
        feature = self.engine.finalize_all()[0]
        self.assertEqual(feature["sample_count"], 2)
        self.assertIn("source_time_gap", feature["quality_flags"])

    def test_missing_sequence_is_flagged(self) -> None:
        self.engine.process_message(
            payload([sample(0, 0.000)], run_id=self.run_id, sequence_id=1)
        )
        feature = self.engine.finalize_all()[0]
        self.assertIn("source_time_gap", feature["quality_flags"])

    def test_identical_qos_batch_duplicate_is_ignored(self) -> None:
        encoded = payload(
            [sample(0, 0.000), sample(1, 1.000)], run_id=self.run_id
        )
        first = self.engine.process_message(encoded)
        duplicate = self.engine.process_message(encoded)
        self.assertEqual(len(first), 1)
        self.assertEqual(duplicate, [])

    def test_conflicting_sequence_duplicate_is_rejected(self) -> None:
        self.engine.process_message(
            payload([sample(0, 0.000)], run_id=self.run_id)
        )
        with self.assertRaisesRegex(ValueError, "sequence_id was reused"):
            self.engine.process_message(
                payload([sample(0, 0.000, 999)], run_id=self.run_id)
            )

    def test_identical_sample_duplicate_in_new_batch_is_ignored(self) -> None:
        duplicate = sample(0, 0.000)
        self.engine.process_message(payload([duplicate], run_id=self.run_id))
        self.engine.process_message(
            payload([duplicate], run_id=self.run_id, sequence_id=1)
        )
        feature = self.engine.finalize_all()[0]
        self.assertEqual(feature["sample_count"], 1)

    def test_non_monotonic_timestamp_is_skipped_and_flagged(self) -> None:
        self.engine.process_message(
            payload(
                [sample(0, 0.012), sample(1, 0.000)], run_id=self.run_id
            )
        )
        feature = self.engine.finalize_all()[0]
        self.assertEqual(feature["sample_count"], 1)
        self.assertIn("source_time_non_monotonic", feature["quality_flags"])
        self.assertIn("invalid_sample", feature["quality_flags"])

    def test_invalid_sample_is_skipped_and_flagged(self) -> None:
        invalid = sample(1, 0.012)
        invalid["acc_x_mg"] = "not-an-integer"
        self.engine.process_message(
            payload([sample(0, 0.000), invalid], run_id=self.run_id)
        )
        feature = self.engine.finalize_all()[0]
        self.assertEqual(feature["sample_count"], 1)
        self.assertIn("invalid_sample", feature["quality_flags"])

    def test_invalid_sample_is_flagged_in_its_source_time_window(self) -> None:
        invalid = sample(2, 1.000)
        invalid["acc_z_mg"] = None
        features = self.engine.process_message(
            payload(
                [sample(0, 0.000), sample(1, 0.999), invalid, sample(3, 1.012)],
                run_id=self.run_id,
            )
        )
        self.assertEqual(len(features), 1)
        self.assertNotIn("invalid_sample", features[0]["quality_flags"])
        final = self.engine.finalize_all()[0]
        self.assertIn("invalid_sample", final["quality_flags"])

    def test_metadata_drift_is_rejected(self) -> None:
        self.engine.process_message(
            payload([sample(0, 0.000)], run_id=self.run_id)
        )
        with self.assertRaisesRegex(ValueError, "metadata changed"):
            self.engine.process_message(
                payload(
                    [sample(1, 0.012)],
                    run_id=self.run_id,
                    sequence_id=1,
                    session_id="different-session",
                )
            )

    def test_unknown_acceleration_unit_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "acceleration_unit must be mg"):
            self.engine.process_message(
                payload(
                    [sample(0, 0.000)],
                    run_id=self.run_id,
                    acceleration_unit="m/s2",
                )
            )

    def test_replay_delivery_timing_cannot_change_features(self) -> None:
        encoded = payload(
            [sample(0, 0.000, 990), sample(1, 0.012, 1010), sample(2, 1.000)],
            run_id=self.run_id,
        )
        immediate = SignalEngine().process_message(encoded)
        delayed = SignalEngine().process_message(encoded)
        self.assertEqual(immediate, delayed)

    def test_finalize_is_idempotent_and_marks_partial_window(self) -> None:
        self.engine.process_message(
            payload([sample(0, 0.000)], run_id=self.run_id)
        )
        feature = self.engine.finalize_all()[0]
        self.assertIn("incomplete_window", feature["quality_flags"])
        self.assertEqual(self.engine.finalize_all(), [])


if __name__ == "__main__":
    unittest.main()
