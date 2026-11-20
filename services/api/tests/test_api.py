from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from roadsense_api.app import app, get_store
from roadsense_api.config import ApiConfig


RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
EVENT_ID = UUID("22222222-2222-4222-8222-222222222222")
NOW = datetime(2026, 10, 19, 5, 51, 57, 52000, tzinfo=timezone.utc)


class FakeStore:
    def ready(self):
        return None

    def sessions(self, limit, offset):
        return ([{
            "session_id": "bumpy-gravel-20261019", "sensor_id": "bosch-xdk-110",
            "source_archive_sha256": "a" * 64, "source_member": "imu/bosch_imu.csv",
            "source_start": NOW, "source_end": NOW.replace(minute=52), "row_count": 62169,
            "road_category": "Bumpy gravel", "orientation_note": "unknown", "run_count": 1,
        }], 1)

    def runs(self, session_id, limit, offset):
        return ([{
            "run_id": RUN_ID, "session_id": "bumpy-gravel-20261019",
            "sensor_id": "bosch-xdk-110", "algorithm_version": "roadsense-vibration-v1",
            "replay_rate": None, "source_start": NOW, "source_end": NOW.replace(second=58),
            "status": "observed", "feature_count": 1, "event_count": 1,
            "created_at": NOW, "updated_at": NOW,
        }], 1)

    def run_exists(self, run_id):
        return run_id == RUN_ID

    def features(self, run_id, limit, offset):
        return ([{
            "run_id": RUN_ID, "window_index": 0,
            "algorithm_version": "roadsense-vibration-v1", "source_start": NOW,
            "source_end": NOW.replace(second=58), "sample_count": 84,
            "vibration_rms_mg": 105.5, "peak_deviation_mg": 201.25,
            "baseline_magnitude_mg": 1001.0, "baseline_method": "window_magnitude_median",
            "quality_flags": [],
        }], 1)

    def events(self, run_id, limit, offset):
        return ([{
            "event_id": EVENT_ID, "run_id": RUN_ID, "window_index": 0,
            "algorithm_version": "roadsense-vibration-v1", "source_start": NOW,
            "source_end": NOW.replace(second=58), "event_type": "high_vibration",
            "heuristic_type": "vibration_rms_threshold", "rule_version": "rule-v1",
            "severity": "high", "threshold_vibration_rms_mg": 100.0,
            "observed_vibration_rms_mg": 105.5, "quality_flags": [], "created_at": NOW,
        }], 1)

    def status(self):
        return {"session_count": 1, "run_count": 1, "feature_count": 1, "event_count": 1,
                "pending_event_publications": 0, "latest_feature_at": NOW}


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_store] = lambda: FakeStore()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()

    def test_health_endpoints(self):
        self.assertEqual(self.client.get("/health/live").json(), {"status": "live"})
        self.assertEqual(self.client.get("/health/ready").json(), {"status": "ready"})

    def test_all_collection_contracts(self):
        for path in (
            "/api/v1/sessions", "/api/v1/runs",
            f"/api/v1/runs/{RUN_ID}/features", f"/api/v1/runs/{RUN_ID}/events",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["count"], 1)
            self.assertEqual(response.json()["total"], 1)

    def test_status_contract(self):
        response = self.client.get("/api/v1/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pending_event_publications"], 0)

    def test_pagination_validation(self):
        self.assertEqual(self.client.get("/api/v1/sessions?limit=0").status_code, 422)
        self.assertEqual(self.client.get("/api/v1/sessions?limit=501").status_code, 422)
        self.assertEqual(self.client.get("/api/v1/sessions?offset=-1").status_code, 422)

    def test_unknown_and_invalid_run(self):
        unknown = "33333333-3333-4333-8333-333333333333"
        self.assertEqual(self.client.get(f"/api/v1/runs/{unknown}/features").status_code, 404)
        self.assertEqual(self.client.get("/api/v1/runs/not-a-uuid/events").status_code, 422)


class ConfigTests(unittest.TestCase):
    def test_password_is_read_from_file_and_not_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            password_file = Path(directory) / "password"
            password_file.write_text("private-value\n", encoding="utf-8")
            config = ApiConfig(
                "db", 5432, "roadsense", "reader", password_file, None, 5
            )
            self.assertEqual(config.password_candidates(), ("private-value",))
            self.assertEqual(
                config.connection_kwargs("private-value")["password"], "private-value"
            )

    def test_password_files_are_reread_and_fallback_is_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            current = Path(directory) / "password"
            previous = Path(directory) / "password.previous"
            current.write_text("old-password\n", encoding="utf-8")
            previous.write_text("future-password\n", encoding="utf-8")
            config = ApiConfig(
                "db", 5432, "roadsense", "reader", current, previous, 5
            )
            self.assertEqual(
                config.password_candidates(), ("old-password", "future-password")
            )
            current.write_text("future-password\n", encoding="utf-8")
            self.assertEqual(config.password_candidates(), ("future-password",))

    def test_password_file_must_contain_exactly_one_nonempty_line(self):
        with tempfile.TemporaryDirectory() as directory:
            password_file = Path(directory) / "password"
            config = ApiConfig(
                "db", 5432, "roadsense", "reader", password_file, None, 5
            )
            for content in ("", "first\nsecond\n"):
                password_file.write_text(content, encoding="utf-8")
                with self.subTest(content=content):
                    with self.assertRaisesRegex(ValueError, "one non-empty line"):
                        config.password_candidates()

    def test_invalid_port_is_rejected(self):
        original = os.environ.get("POSTGRES_PORT")
        os.environ["POSTGRES_PORT"] = "70000"
        try:
            with self.assertRaisesRegex(ValueError, "between 1 and 65535"):
                ApiConfig.from_env()
        finally:
            if original is None:
                os.environ.pop("POSTGRES_PORT", None)
            else:
                os.environ["POSTGRES_PORT"] = original


if __name__ == "__main__":
    unittest.main()
