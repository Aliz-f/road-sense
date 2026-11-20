from __future__ import annotations

import os

from roadsense_dashboard.charts import vibration_figure
from roadsense_dashboard.client import ApiClient


def main() -> int:
    run_id = os.environ["EXPECTED_RUN_ID"]
    expected_features = int(os.environ["EXPECTED_FEATURES"])
    expected_events = int(os.environ["EXPECTED_EVENTS"])
    client = ApiClient(os.environ.get("API_INTERNAL_URL", "http://api:8000"))
    features = client.features(run_id)
    events = client.events(run_id)
    if len(features) != expected_features or len(events) != expected_events:
        raise AssertionError(f"unexpected dashboard data: {len(features)} features, {len(events)} events")
    figure = vibration_figure(features, events)
    expected_traces = 3 if expected_events else 2
    if len(figure.data) != expected_traces or len(figure.data[0].x) != expected_features:
        raise AssertionError("dashboard figure does not contain the expected real-data traces")
    if expected_events and len(figure.data[2].x) != expected_events:
        raise AssertionError("dashboard event trace does not contain every API event")
    print("Phase 05 dashboard API client and Plotly real-data rendering: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
