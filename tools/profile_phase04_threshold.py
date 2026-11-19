#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import tarfile
from datetime import datetime
from pathlib import Path


RECORDINGS = (
    ("bumpy-gravel-20261019", "Bumpy Gravel - imu.tar", "imu/bosch_imu.csv"),
    ("paved-road-60kmh-20261007", "Paved Road 60kmh - imu.tar", "imu/bosch_imu.csv"),
    ("highway-20261007", "Highway - imu.tar", "imu/bosch.csv"),
)


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def profile(archive: Path, member: str, threshold: float) -> dict[str, object]:
    windows: dict[int, list[float]] = {}
    anchor = None
    with tarfile.open(archive) as tar:
        extracted = tar.extractfile(member)
        if extracted is None:
            raise ValueError(f"missing archive member: {member}")
        rows = csv.DictReader(line.decode("utf-8") for line in extracted)
        for row in rows:
            source_time = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            if anchor is None:
                anchor = source_time
            window_index = int((source_time - anchor).total_seconds())
            magnitude = math.sqrt(
                int(row["acc_x_mg"]) ** 2
                + int(row["acc_y_mg"]) ** 2
                + int(row["acc_z_mg"]) ** 2
            )
            windows.setdefault(window_index, []).append(magnitude)
    rms_values = []
    for magnitudes in windows.values():
        baseline = statistics.median(magnitudes)
        rms_values.append(
            math.sqrt(
                sum((value - baseline) ** 2 for value in magnitudes) / len(magnitudes)
            )
        )
    return {
        "window_count": len(rms_values),
        "rms_min_mg": min(rms_values),
        "rms_p50_mg": percentile(rms_values, 0.50),
        "rms_p90_mg": percentile(rms_values, 0.90),
        "rms_p95_mg": percentile(rms_values, 0.95),
        "rms_p99_mg": percentile(rms_values, 0.99),
        "rms_max_mg": max(rms_values),
        "threshold_mg": threshold,
        "event_count": sum(value >= threshold for value in rms_values),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archives", type=Path, required=True)
    parser.add_argument("--threshold-mg", type=float, default=100.0)
    args = parser.parse_args()
    if not math.isfinite(args.threshold_mg) or args.threshold_mg <= 0:
        parser.error("--threshold-mg must be finite and positive")
    result = {
        session_id: profile(args.archives / archive_name, member, args.threshold_mg)
        for session_id, archive_name, member in RECORDINGS
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
