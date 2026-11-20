from __future__ import annotations

import os

from roadsense_dashboard.charts import vibration_figure
from roadsense_dashboard.client import ApiClient


def main() -> int:
    run_id = os.environ["EXPECTED_RUN_ID"]
    client = ApiClient(os.environ.get("API_INTERNAL_URL", "http://api:8000"))
    features = client.features(run_id)
    events = client.events(run_id)
    if len(features) != 19 or len(events) != 5:
        raise AssertionError(f"unexpected dashboard data: {len(features)} features, {len(events)} events")
    figure = vibration_figure(features, events)
    if len(figure.data) != 3 or len(figure.data[0].x) != 19 or len(figure.data[2].x) != 5:
        raise AssertionError("dashboard figure does not contain the expected real-data traces")
    print("Phase 05 dashboard API client and Plotly real-data rendering: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
