from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

from roadsense_dashboard.charts import vibration_figure
from roadsense_dashboard.client import ApiClient


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
    def test_dashboard_handles_unavailable_api_and_shows_methodology_warning(self):
        app_path = os.path.join(os.path.dirname(__file__), "..", "src", "roadsense_dashboard", "app.py")
        previous = os.environ.get("API_INTERNAL_URL")
        os.environ["API_INTERNAL_URL"] = "http://127.0.0.1:9"
        try:
            test_app = AppTest.from_file(app_path, default_timeout=5).run()
        finally:
            if previous is None:
                os.environ.pop("API_INTERNAL_URL", None)
            else:
                os.environ["API_INTERNAL_URL"] = previous
        self.assertEqual(len(test_app.exception), 0)
        self.assertTrue(any("not scientifically validated potholes" in item.value for item in test_app.warning))
        self.assertTrue(any("API is unavailable" in item.value for item in test_app.error))


if __name__ == "__main__":
    unittest.main()
