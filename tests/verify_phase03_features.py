#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import tarfile
from datetime import datetime, timedelta
from pathlib import Path


def completed_features(path: Path) -> list[dict[str, object]]:
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("event") == "feature_subscriber_complete":
            return record["features"]
    raise ValueError(f"no feature_subscriber_complete record in {path}")


def source_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_time(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def reference_windows(
    archive: Path, member: str, max_samples: int
) -> list[dict[str, object]]:
    windows: dict[int, list[float]] = {}
    anchor: datetime | None = None
    with tarfile.open(archive, mode="r") as tar:
        extracted = tar.extractfile(member)
        if extracted is None:
            raise ValueError(f"missing tar member: {member}")
        rows = csv.DictReader(line.decode("utf-8") for line in extracted)
        for sample_index, row in enumerate(rows):
            if sample_index >= max_samples:
                break
            timestamp = source_time(row["timestamp"])
            if anchor is None:
                anchor = timestamp
            window_index = int((timestamp - anchor).total_seconds())
            magnitude = math.sqrt(
                int(row["acc_x_mg"]) ** 2
                + int(row["acc_y_mg"]) ** 2
                + int(row["acc_z_mg"]) ** 2
            )
            windows.setdefault(window_index, []).append(magnitude)
    if anchor is None or len(windows) < 2:
        raise ValueError("reference source did not contain complete windows")

    completed: list[dict[str, object]] = []
    final_index = max(windows)
    for window_index in sorted(index for index in windows if index != final_index):
        magnitudes = windows[window_index]
        baseline = float(statistics.median(magnitudes))
        deviations = [value - baseline for value in magnitudes]
        start = anchor + timedelta(seconds=window_index)
        completed.append(
            {
                "window_index": window_index,
                "source_start": format_time(start),
                "source_end": format_time(start + timedelta(seconds=1)),
                "sample_count": len(magnitudes),
                "vibration_rms_mg": math.sqrt(
                    sum(value * value for value in deviations) / len(deviations)
                ),
                "peak_deviation_mg": max(abs(value) for value in deviations),
                "baseline_magnitude_mg": baseline,
                "quality_flags": [],
            }
        )
    return completed


def compare_runs(
    unpaced: list[dict[str, object]], paced: list[dict[str, object]]
) -> None:
    if len(unpaced) != len(paced):
        raise AssertionError("replay rates produced different feature counts")
    for first, second in zip(unpaced, paced, strict=True):
        first_without_run = {key: value for key, value in first.items() if key != "run_id"}
        second_without_run = {
            key: value for key, value in second.items() if key != "run_id"
        }
        if first_without_run != second_without_run:
            raise AssertionError("replay rate changed a feature payload")


def compare_reference(
    actual: list[dict[str, object]], expected: list[dict[str, object]]
) -> None:
    if len(actual) != len(expected):
        raise AssertionError(
            f"expected {len(expected)} completed windows, got {len(actual)}"
        )
    numeric_fields = (
        "vibration_rms_mg",
        "peak_deviation_mg",
        "baseline_magnitude_mg",
    )
    exact_fields = (
        "window_index",
        "source_start",
        "source_end",
        "sample_count",
        "quality_flags",
    )
    for actual_window, expected_window in zip(actual, expected, strict=True):
        for field in exact_fields:
            if actual_window[field] != expected_window[field]:
                raise AssertionError(
                    f"window {expected_window['window_index']} differs for {field}: "
                    f"{actual_window[field]!r} != {expected_window[field]!r}"
                )
        for field in numeric_fields:
            if not math.isclose(
                actual_window[field], expected_window[field], rel_tol=1e-12, abs_tol=1e-12
            ):
                raise AssertionError(
                    f"window {expected_window['window_index']} differs for {field}: "
                    f"{actual_window[field]!r} != {expected_window[field]!r}"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unpaced-log", required=True, type=Path)
    parser.add_argument("--paced-log", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--member", default="imu/bosch_imu.csv")
    parser.add_argument("--max-samples", default=256, type=int)
    args = parser.parse_args()

    unpaced = completed_features(args.unpaced_log)
    paced = completed_features(args.paced_log)
    expected = reference_windows(args.archive, args.member, args.max_samples)
    compare_runs(unpaced, paced)
    compare_reference(unpaced, expected)
    print(
        json.dumps(
            {
                "event": "phase03_reference_verified",
                "windows": [
                    {
                        "window_index": item["window_index"],
                        "sample_count": item["sample_count"],
                        "vibration_rms_mg": item["vibration_rms_mg"],
                        "peak_deviation_mg": item["peak_deviation_mg"],
                        "baseline_magnitude_mg": item["baseline_magnitude_mg"],
                    }
                    for item in expected
                ],
            },
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
