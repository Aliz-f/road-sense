#!/usr/bin/env python3
"""Produce a Phase 00 summary from the private MUHOS archives.

The archives are intentionally read in place and are never extracted or copied
into the repository.  The output is JSON so that the checked-in dataset profile
can be regenerated without third-party packages.
"""

from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import statistics
import tarfile
from html import escape
from pathlib import Path
from typing import Any


UTC = dt.timezone.utc


def iso_utc(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_csv_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("no values")
    index = (len(ordered) - 1) * fraction
    low, high = int(index), min(int(index) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def member_for(archive: tarfile.TarFile, suffix: str) -> tarfile.TarInfo:
    members = [member for member in archive.getmembers() if member.isfile() and member.name.endswith(suffix)]
    if len(members) != 1:
        raise ValueError(f"expected one {suffix} member, found {len(members)}")
    return members[0]


def inspect_imu(path: Path) -> dict[str, Any]:
    with tarfile.open(path) as archive:
        member = member_for(archive, ".csv")
        raw = archive.extractfile(member)
        if raw is None:
            raise ValueError(f"cannot read {member.name}")
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
        headers = reader.fieldnames or []
        missing = collections.Counter()
        numeric = {header: [] for header in headers if header != "timestamp"}
        first: dt.datetime | None = None
        last: dt.datetime | None = None
        previous: dt.datetime | None = None
        intervals_ms: list[float] = []
        duplicate_timestamps = 0
        non_increasing_timestamps = 0
        row_count = 0
        for row in reader:
            row_count += 1
            for header in headers:
                if not row.get(header, "").strip():
                    missing[header] += 1
            timestamp = parse_csv_time(row["timestamp"])
            first = timestamp if first is None else first
            last = timestamp
            if previous is not None:
                interval = (timestamp - previous).total_seconds() * 1000
                intervals_ms.append(interval)
                if interval == 0:
                    duplicate_timestamps += 1
                if interval <= 0:
                    non_increasing_timestamps += 1
            previous = timestamp
            for header, values in numeric.items():
                value = row.get(header, "")
                if value.strip():
                    values.append(float(value))
        positive = [value for value in intervals_ms if value > 0]
        median_interval = statistics.median(positive)
        nominal_rate = 1000 / median_interval
        gaps_over_1_5x = sum(value > 1.5 * median_interval for value in positive)
        numeric_summary = {
            header: {"min": min(values), "max": max(values), "mean": statistics.fmean(values)}
            for header, values in numeric.items()
            if values
        }
        return {
            "archive": path.name,
            "archive_size_bytes": path.stat().st_size,
            "archive_sha256": sha256(path),
            "bosch_member": member.name,
            "bosch_member_size_bytes": member.size,
            "columns": headers,
            "row_count": row_count,
            "timestamp_start_utc": iso_utc(first) if first else None,
            "timestamp_end_utc": iso_utc(last) if last else None,
            "duration_seconds": (last - first).total_seconds() if first and last else None,
            "missing_cells_by_column": dict(missing),
            "interval_ms": {
                "min": min(positive),
                "p50": median_interval,
                "p95": percentile(positive, 0.95),
                "max": max(positive),
                "estimated_hz_from_p50": nominal_rate,
                "duplicate_timestamp_intervals": duplicate_timestamps,
                "non_increasing_timestamp_intervals": non_increasing_timestamps,
                "gaps_over_1_5x_p50": gaps_over_1_5x,
            },
            "numeric_summary": numeric_summary,
        }


def inspect_can(path: Path) -> dict[str, Any]:
    with tarfile.open(path) as archive:
        members = [member for member in archive.getmembers()
                   if member.isfile() and "/toyota_CAN_" in member.name and member.name.endswith(".json")]
        if len(members) != 1:
            raise ValueError(f"expected one decoded Toyota CAN member, found {len(members)}")
        member = members[0]
        raw = archive.extractfile(member)
        if raw is None:
            raise ValueError(f"cannot read {member.name}")
        records = json.load(io.TextIOWrapper(raw, encoding="utf-8"))
    speed = [record for record in records if record.get("message") == "SPEED" and record.get("signal") == "SPEED"]
    timestamps = [float(record["timestamp"]) for record in records]
    speed_timestamps = [float(record["timestamp"]) for record in speed]
    speed_values = [float(record["value"]) for record in speed]
    speed_intervals = [later - earlier for earlier, later in zip(speed_timestamps, speed_timestamps[1:])]
    signals = collections.Counter((record.get("message"), record.get("signal")) for record in records)
    return {
        "archive": path.name,
        "archive_size_bytes": path.stat().st_size,
        "archive_sha256": sha256(path),
        "can_member": member.name,
        "can_member_size_bytes": member.size,
        "record_count": len(records),
        "timestamp_start_unix": min(timestamps),
        "timestamp_end_unix": max(timestamps),
        "timestamp_start_utc_assuming_unix": iso_utc(dt.datetime.fromtimestamp(min(timestamps), UTC)),
        "timestamp_end_utc_assuming_unix": iso_utc(dt.datetime.fromtimestamp(max(timestamps), UTC)),
        "speed": {
            "record_count": len(speed),
            "min": min(speed_values),
            "max": max(speed_values),
            "mean": statistics.fmean(speed_values),
            "timestamp_start_utc_assuming_unix": iso_utc(dt.datetime.fromtimestamp(min(speed_timestamps), UTC)),
            "timestamp_end_utc_assuming_unix": iso_utc(dt.datetime.fromtimestamp(max(speed_timestamps), UTC)),
            "interval_seconds_p50": statistics.median(speed_intervals),
            "unit": "not encoded in the archive; unverified",
        },
        "signal_pairs": [{"message": message, "signal": signal, "count": count}
                         for (message, signal), count in sorted(signals.items())],
    }


def overlap(imu: dict[str, Any], can: dict[str, Any]) -> dict[str, Any]:
    imu_start = parse_csv_time(imu["timestamp_start_utc"])
    imu_end = parse_csv_time(imu["timestamp_end_utc"])
    can_start = dt.datetime.fromtimestamp(can["timestamp_start_unix"], UTC)
    can_end = dt.datetime.fromtimestamp(can["timestamp_end_unix"], UTC)
    start, end = max(imu_start, can_start), min(imu_end, can_end)
    return {
        "overlap_seconds_assuming_can_unix_utc": max(0.0, (end - start).total_seconds()),
        "imu_starts_after_can_seconds_assuming_can_unix_utc": (imu_start - can_start).total_seconds(),
        "imu_ends_before_can_seconds_assuming_can_unix_utc": (can_end - imu_end).total_seconds(),
    }


def write_imu_summary_svg(imu: dict[str, Any], output: Path) -> None:
    """Write a small aggregate-only SVG; it contains no source samples."""
    names = [("bumpy_gravel", "Bumpy gravel"),
             ("paved_road_60kmh", "Paved road 60 km/h"),
             ("highway", "Highway")]
    max_duration = max(imu[key]["duration_seconds"] for key, _ in names)
    bars = []
    for index, (key, label) in enumerate(names):
        item = imu[key]
        y = 58 + index * 68
        width = 440 * item["duration_seconds"] / max_duration
        rate = item["interval_ms"]["estimated_hz_from_p50"]
        bars.append(
            f'<text x="20" y="{y}" font-size="14">{escape(label)}</text>'
            f'<rect x="180" y="{y - 17}" width="{width:.1f}" height="24" fill="#2563eb"/>'
            f'<text x="{188 + width:.1f}" y="{y}" font-size="12">'
            f'{item["row_count"]:,} rows · {item["duration_seconds"]:.3f} s · {rate:.1f} Hz</text>'
        )
    content = "\n".join(bars)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" width="820" height="280" role="img"
  aria-labelledby="title desc">
  <title id="title">MUHOS Bosch IMU recording summary</title>
  <desc id="desc">Aggregate Phase 00 summary of row count, duration and median-derived sampling rate.</desc>
  <rect width="100%" height="100%" fill="white"/>
  <text x="20" y="28" font-size="20" font-family="sans-serif" font-weight="bold">MUHOS Bosch IMU recordings</text>
""" + content + "\n</svg>\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archives", type=Path, default=Path("data/raw/archives"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/roadsense-muhos-profile.json"))
    parser.add_argument("--plot", type=Path, help="Optional aggregate-only SVG output path")
    args = parser.parse_args()
    archives = args.archives
    imu = {
        "bumpy_gravel": inspect_imu(archives / "Bumpy Gravel - imu.tar"),
        "paved_road_60kmh": inspect_imu(archives / "Paved Road 60kmh - imu.tar"),
        "highway": inspect_imu(archives / "Highway - imu.tar"),
    }
    can = {
        "bumpy_gravel": inspect_can(archives / "Bumpy Gravel - can.tar"),
        "paved_road_60kmh": inspect_can(archives / "Paved Road 60kmh - can.tar"),
    }
    report = {"imu": imu, "can": can,
              "can_imu_overlap": {key: overlap(imu[key], can[key]) for key in can}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.plot:
        write_imu_summary_svg(imu, args.plot)
    print(args.output)


if __name__ == "__main__":
    main()
