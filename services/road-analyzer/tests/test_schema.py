from __future__ import annotations

import json
import math
import unittest

from helpers import encoded_feature, feature_payload
from road_analyzer.schema import parse_feature_message


class FeatureSchemaTests(unittest.TestCase):
    def test_valid_feature_is_parsed(self) -> None:
        feature = parse_feature_message(encoded_feature())
        self.assertEqual(feature.window_index, 0)
        self.assertEqual(feature.sample_count, 84)
        self.assertEqual(feature.vibration_rms_mg, 101.25)
        self.assertEqual(len(feature.payload_sha256), 64)

    def test_payload_digest_is_canonical(self) -> None:
        payload = feature_payload()
        first = json.dumps(payload, sort_keys=False).encode()
        second = json.dumps(payload, sort_keys=True, indent=2).encode()
        self.assertEqual(
            parse_feature_message(first).payload_sha256,
            parse_feature_message(second).payload_sha256,
        )

    def test_missing_and_unknown_fields_are_rejected(self) -> None:
        payload = feature_payload(extra=True)
        payload.pop("sample_count")
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            parse_feature_message(json.dumps(payload).encode())

    def test_duplicate_json_field_is_rejected(self) -> None:
        encoded = encoded_feature()[:-1] + b',"sample_count":84}'
        with self.assertRaisesRegex(ValueError, "duplicate JSON field"):
            parse_feature_message(encoded)

    def test_noncanonical_uuid_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "canonical lowercase"):
            parse_feature_message(
                encoded_feature(run_id="44444444-4444-4444-8444-44444444444A")
            )

    def test_nonfinite_metric_is_rejected(self) -> None:
        for value in (math.nan, math.inf, -1.0, True):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_feature_message(encoded_feature(vibration_rms_mg=value))

    def test_window_must_be_exactly_one_second(self) -> None:
        with self.assertRaisesRegex(ValueError, "exactly one second"):
            parse_feature_message(encoded_feature(source_end="2026-10-19T05:51:59.052Z"))

    def test_quality_flags_must_be_known_unique_and_ordered(self) -> None:
        invalid = (
            ["unknown"],
            ["incomplete_window", "source_time_gap"],
            ["source_time_gap", "source_time_gap"],
        )
        for flags in invalid:
            with self.subTest(flags=flags):
                with self.assertRaisesRegex(ValueError, "quality_flags"):
                    parse_feature_message(encoded_feature(quality_flags=flags))

    def test_ordered_quality_flags_are_accepted(self) -> None:
        feature = parse_feature_message(
            encoded_feature(quality_flags=["source_time_gap", "incomplete_window"])
        )
        self.assertEqual(feature.quality_flags, ("source_time_gap", "incomplete_window"))

    def test_wrong_algorithm_and_baseline_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "algorithm_version"):
            parse_feature_message(encoded_feature(algorithm_version="future"))
        with self.assertRaisesRegex(ValueError, "baseline_method"):
            parse_feature_message(encoded_feature(baseline_method="mean"))


if __name__ == "__main__":
    unittest.main()
