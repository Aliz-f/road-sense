#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import urllib.request
from datetime import datetime
from pathlib import Path

from verify_phase03_features import reference_windows


def get_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=10) as response:
        if response.status != 200:
            raise AssertionError(f"unexpected HTTP status {response.status}: {url}")
        return json.load(response)


def normalized_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--member", default="imu/bosch_imu.csv")
    parser.add_argument("--max-samples", default=1536, type=int)
    args = parser.parse_args()

    expected = reference_windows(args.archive, args.member, args.max_samples)
    features_page = get_json(
        f"{args.base_url}/api/v1/runs/{args.run_id}/features?limit=500&offset=0"
    )
    events_page = get_json(
        f"{args.base_url}/api/v1/runs/{args.run_id}/events?limit=500&offset=0"
    )
    runs_page = get_json(f"{args.base_url}/api/v1/runs?limit=500&offset=0")
    status = get_json(f"{args.base_url}/api/v1/status")
    actual = features_page["items"]
    if features_page["total"] != len(expected) or len(actual) != len(expected):
        raise AssertionError("API feature pagination total does not match real-data reference")
    if events_page["total"] != 5:
        raise AssertionError(f"expected 5 threshold events, got {events_page['total']}")
    if [item["window_index"] for item in events_page["items"]] != [13, 14, 15, 16, 18]:
        raise AssertionError("API returned unexpected event windows")
    if not any(item["run_id"] == args.run_id for item in runs_page["items"]):
        raise AssertionError("run listing omitted the replay run")
    if status["pending_event_publications"] != 0:
        raise AssertionError("event outbox still has pending rows")

    for observed, reference in zip(actual, expected, strict=True):
        for field in ("window_index", "sample_count", "quality_flags"):
            if observed[field] != reference[field]:
                raise AssertionError(f"window differs for {field}")
        for field in ("source_start", "source_end"):
            if normalized_time(observed[field]) != normalized_time(reference[field]):
                raise AssertionError(f"window differs for {field}")
        for field in ("vibration_rms_mg", "peak_deviation_mg", "baseline_magnitude_mg"):
            if not math.isclose(observed[field], reference[field], rel_tol=1e-12, abs_tol=1e-12):
                raise AssertionError(f"window differs for {field}")

    print(json.dumps({
        "event": "phase05_api_reference_verified", "run_id": args.run_id,
        "features": len(actual), "events": events_page["total"],
    }, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
