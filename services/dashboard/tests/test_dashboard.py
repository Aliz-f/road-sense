from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from roadsense_dashboard.charts import vibration_figure
from roadsense_dashboard.client import ApiClient


APP_PATH = os.path.join(
    os.path.dirname(__file__), "..", "src", "roadsense_dashboard", "app.py"
)
SESSIONS = [
    {
        "session_id": "paved-road-60kmh-20261007",
        "road_category": "Paved road 60kmh recording label",
        "sensor_id": "bosch-xdk-110",
        "source_archive_sha256": "a" * 64,
        "source_member": "imu/bosch_imu.csv",
        "source_start": "2026-10-07T09:52:42.239Z",
        "source_end": "2026-10-07T10:02:22.696Z",
        "row_count": 48363,
        "orientation_note": "Sensor orientation relative to the vehicle is unknown.",
    },
    {
        "session_id": "bumpy-gravel-20261019",
        "road_category": "Bumpy gravel",
        "sensor_id": "bosch-xdk-110",
        "source_archive_sha256": "b" * 64,
        "source_member": "imu/bosch_imu.csv",
        "source_start": "2026-10-19T05:51:57.052Z",
        "source_end": "2026-10-19T06:04:23.585Z",
        "row_count": 62169,
        "orientation_note": "Sensor orientation relative to the vehicle is unknown.",
    },
]
RUNS = {
    "paved-road-60kmh-20261007": [{
        "run_id": "11111111-1111-4111-8111-111111111111",
        "source_start": "2026-10-07T09:52:42.239Z",
        "status": "observed",
        "algorithm_version": "roadsense-vibration-v1",
    }],
    "bumpy-gravel-20261019": [
        {
            "run_id": "22222222-2222-4222-8222-222222222222",
            "source_start": "2026-10-19T05:51:57.052Z",
            "status": "observed",
            "algorithm_version": "roadsense-vibration-v1",
        },
        {
            "run_id": "33333333-3333-4333-8333-333333333333",
            "source_start": "2026-10-19T05:52:57.052Z",
            "status": "observed",
            "algorithm_version": "roadsense-vibration-v1",
        },
    ],
}
FEATURES = [{
    "source_start": "2026-10-19T05:51:57.052Z",
    "vibration_rms_mg": 105.5,
    "peak_deviation_mg": 201.0,
}]
EVENTS = [{
    "source_start": "2026-10-19T05:51:57.052Z",
    "window_index": 0,
    "observed_vibration_rms_mg": 105.5,
    "threshold_vibration_rms_mg": 100.0,
    "quality_flags": ["incomplete_window"],
    "rule_version": "roadsense-high-vibration-rms-v1-t100",
}]


class ClientTests(unittest.TestCase):
    @patch("roadsense_dashboard.client.requests.get")
    def test_all_pages_preserves_filter_and_advances_offset(self, request_get):
        first = Mock()
        first.raise_for_status.return_value = None
        first.json.return_value = {"items": [{"run_id": "one"}], "total": 2}
        second = Mock()
        second.raise_for_status.return_value = None
        second.json.return_value = {"items": [{"run_id": "two"}], "total": 2}
        request_get.side_effect = [first, second]
        items = ApiClient("http://api:8000").runs("session-one")
        self.assertEqual([item["run_id"] for item in items], ["one", "two"])
        self.assertEqual(request_get.call_args_list[0].kwargs["params"]["session_id"], "session-one")
        self.assertEqual(request_get.call_args_list[1].kwargs["params"]["offset"], 1)

    @patch("roadsense_dashboard.client.requests.get")
    def test_invalid_page_contract_is_rejected(self, request_get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"items": "wrong", "total": 1}
        request_get.return_value = response
        with self.assertRaisesRegex(ValueError, "missing items"):
            ApiClient("http://api:8000").sessions()


class ChartTests(unittest.TestCase):
    def test_chart_contains_metrics_and_event_overlay(self):
        features = [{"source_start": "2026-10-19T05:51:57.052Z", "vibration_rms_mg": 105.5,
                     "peak_deviation_mg": 201.0}]
        events = [{"source_start": "2026-10-19T05:51:57.052Z", "observed_vibration_rms_mg": 105.5}]
        figure = vibration_figure(features, events)
        self.assertEqual(len(figure.data), 3)
        self.assertEqual(figure.layout.yaxis.title.text, "Acceleration metric (mg)")
        self.assertIn("Exploratory", figure.data[2].name)


class StreamlitSmokeTests(unittest.TestCase):
    def successful_app(self):
        status = {
            "run_count": 3,
            "feature_count": 38,
            "event_count": 5,
            "pending_event_publications": 0,
        }
        with (
            patch.object(ApiClient, "status", return_value=status),
            patch.object(ApiClient, "sessions", return_value=SESSIONS),
            patch.object(ApiClient, "runs", side_effect=lambda session_id: RUNS[session_id]),
            patch.object(ApiClient, "features", return_value=FEATURES),
            patch.object(ApiClient, "events", return_value=EVENTS),
        ):
            return AppTest.from_file(APP_PATH, default_timeout=5).run()

    def test_successful_dashboard_selection_statistics_chart_and_events(self):
        test_app = self.successful_app()
        self.assertEqual(len(test_app.exception), 0)
        self.assertEqual(
            [(metric.label, metric.value) for metric in test_app.metric],
            [
                ("Observed runs", "3"),
                ("Feature windows", "38"),
                ("Vibration events", "5"),
                ("Pending event publishes", "0"),
            ],
        )
        self.assertEqual(len(test_app.selectbox), 2)
        self.assertEqual(len(test_app.selectbox[0].options), 2)
        self.assertIn("Paved road", test_app.selectbox[0].value)
        self.assertEqual(len(test_app.get("plotly_chart")), 1)
        self.assertEqual(len(test_app.dataframe), 1)
        event_table = test_app.dataframe[0].value
        self.assertEqual(event_table.iloc[0]["observed_rms_mg"], 105.5)
        self.assertEqual(event_table.iloc[0]["window_index"], 0)
        self.assertTrue(any("Exploratory high-vibration events" in item.value
                            for item in test_app.subheader))

    def test_recording_and_run_selection_rerenders_successfully(self):
        status = {
            "run_count": 3, "feature_count": 38, "event_count": 5,
            "pending_event_publications": 0,
        }
        with (
            patch.object(ApiClient, "status", return_value=status),
            patch.object(ApiClient, "sessions", return_value=SESSIONS),
            patch.object(ApiClient, "runs", side_effect=lambda session_id: RUNS[session_id]),
            patch.object(ApiClient, "features", return_value=FEATURES) as features,
            patch.object(ApiClient, "events", return_value=EVENTS) as events,
        ):
            test_app = AppTest.from_file(APP_PATH, default_timeout=5).run()
            test_app.selectbox[0].select(SESSIONS[1]["road_category"] + " — " +
                                         SESSIONS[1]["session_id"]).run()
            self.assertEqual(len(test_app.selectbox[1].options), 2)
            second_run_label = test_app.selectbox[1].options[1]
            test_app.selectbox[1].select(second_run_label).run()
        self.assertEqual(len(test_app.exception), 0)
        self.assertEqual(test_app.selectbox[1].value, second_run_label)
        self.assertIn("1 feature windows · 1 events", test_app.caption[0].value)
        self.assertEqual(features.call_args.args[0], RUNS["bumpy-gravel-20261019"][1]["run_id"])
        self.assertEqual(events.call_args.args[0], RUNS["bumpy-gravel-20261019"][1]["run_id"])

    def test_dashboard_handles_unavailable_api_and_shows_methodology_warning(self):
        previous = os.environ.get("API_INTERNAL_URL")
        os.environ["API_INTERNAL_URL"] = "http://127.0.0.1:9"
        try:
            test_app = AppTest.from_file(APP_PATH, default_timeout=5).run()
        finally:
            if previous is None:
                os.environ.pop("API_INTERNAL_URL", None)
            else:
                os.environ["API_INTERNAL_URL"] = previous
        self.assertEqual(len(test_app.exception), 0)
        self.assertTrue(any("not scientifically validated potholes" in item.value for item in test_app.warning))
        self.assertTrue(any("API is unavailable" in item.value for item in test_app.error))

    def test_dashboard_handles_run_list_failure(self):
        with (
            patch.object(ApiClient, "status", return_value={
                "run_count": 1, "feature_count": 1, "event_count": 0,
                "pending_event_publications": 0,
            }),
            patch.object(ApiClient, "sessions", return_value=SESSIONS[:1]),
            patch.object(ApiClient, "runs", side_effect=ValueError("invalid run page")),
        ):
            test_app = AppTest.from_file(APP_PATH, default_timeout=5).run()
        self.assertEqual(len(test_app.exception), 0)
        self.assertTrue(any("Could not load runs" in item.value for item in test_app.error))


if __name__ == "__main__":
    unittest.main()
