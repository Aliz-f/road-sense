from __future__ import annotations

import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from helpers import encoded_feature
from road_analyzer.registry import SessionRegistry
from road_analyzer.schema import parse_feature_message


REGISTRY_PATH = Path("/app/session-registry.json")


class SessionRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = SessionRegistry.load(REGISTRY_PATH)

    def test_verified_registry_contains_all_three_sessions(self) -> None:
        self.assertEqual(len(self.registry.sessions), 3)
        session = self.registry.sessions["bumpy-gravel-20261019"]
        self.assertEqual(session.row_count, 62169)
        self.assertEqual(session.source_member, "imu/bosch_imu.csv")

    def test_matching_provenance_and_window_anchor_are_accepted(self) -> None:
        feature = parse_feature_message(encoded_feature())
        session = self.registry.match(feature)
        self.assertEqual(session.session_id, feature.session_id)

    def test_unknown_session_is_rejected(self) -> None:
        feature = parse_feature_message(encoded_feature(session_id="missing"))
        with self.assertRaisesRegex(ValueError, "unknown session_id"):
            self.registry.match(feature)

    def test_conflicting_provenance_is_rejected(self) -> None:
        feature = parse_feature_message(encoded_feature(source_archive_sha256="a" * 64))
        with self.assertRaisesRegex(ValueError, "provenance conflicts"):
            self.registry.match(feature)

    def test_wrong_window_anchor_is_rejected(self) -> None:
        feature = parse_feature_message(encoded_feature(window_index=1))
        with self.assertRaisesRegex(ValueError, "session anchor"):
            self.registry.match(feature)

    def test_later_window_matches_exact_session_anchor(self) -> None:
        session = self.registry.sessions["bumpy-gravel-20261019"]
        start = session.source_start + timedelta(seconds=13)
        end = start + timedelta(seconds=1)
        feature = parse_feature_message(
            encoded_feature(
                window_index=13,
                source_start=start.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                source_end=end.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            )
        )
        self.assertEqual(self.registry.match(feature), session)

    def test_duplicate_registry_id_is_rejected(self) -> None:
        raw = json.loads(REGISTRY_PATH.read_text())
        raw.append(raw[0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "duplicate session"):
                SessionRegistry.load(path)


if __name__ == "__main__":
    unittest.main()
