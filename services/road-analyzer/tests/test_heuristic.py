from __future__ import annotations

import unittest

from helpers import encoded_feature
from road_analyzer.heuristic import build_event, is_high_vibration
from road_analyzer.schema import parse_feature_message, validate_event_payload


class HeuristicTests(unittest.TestCase):
    def test_threshold_is_inclusive(self) -> None:
        feature = parse_feature_message(encoded_feature(vibration_rms_mg=100.0))
        self.assertTrue(is_high_vibration(feature, 100.0))
        self.assertFalse(is_high_vibration(feature, 100.0001))

    def test_event_is_contract_valid_and_traceable(self) -> None:
        feature = parse_feature_message(encoded_feature())
        event = build_event(feature, 100.0, "roadsense-high-vibration-rms-v1-t100")
        validate_event_payload(event)
        self.assertEqual(event["run_id"], feature.run_id)
        self.assertEqual(event["window_index"], feature.window_index)
        self.assertEqual(event["observed_vibration_rms_mg"], 101.25)

    def test_event_id_is_deterministic_and_rule_specific(self) -> None:
        feature = parse_feature_message(encoded_feature())
        first = build_event(feature, 100.0, "rule-a")
        second = build_event(feature, 100.0, "rule-a")
        changed = build_event(feature, 125.0, "rule-b")
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertNotEqual(first["event_id"], changed["event_id"])


if __name__ == "__main__":
    unittest.main()
