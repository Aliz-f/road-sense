from __future__ import annotations

import csv
import hashlib
import io
import tarfile
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from .model import ImuSample


EXPECTED_COLUMNS = (
    "timestamp",
    "acc_x_mg",
    "acc_y_mg",
    "acc_z_mg",
    "mag_x_uT",
    "mag_y_uT",
    "mag_z_uT",
    "mag_r_uT",
    "gyro_x_mdeg",
    "gyro_y_mdeg",
    "gyro_z_mdeg",
)
NUMERIC_COLUMNS = EXPECTED_COLUMNS[1:]


class SourceDataError(ValueError):
    """The source archive does not satisfy the verified Phase 00 contract."""


def archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_source_timestamp(value: str) -> datetime:
    if not value or not value.endswith("Z"):
        raise SourceDataError(f"timestamp is not UTC RFC 3339 with Z: {value!r}")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise SourceDataError(f"invalid source timestamp: {value!r}") from error
    if parsed.tzinfo != timezone.utc:
        raise SourceDataError(f"timestamp is not UTC: {value!r}")
    return parsed


def iter_imu_samples(
    archive_path: Path,
    member_name: str,
    expected_sha256: str,
    max_samples: int = 0,
) -> Iterator[ImuSample]:
    actual_sha256 = archive_sha256(archive_path)
    if actual_sha256 != expected_sha256:
        raise SourceDataError(
            f"archive SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )

    with tarfile.open(archive_path, mode="r") as archive:
        try:
            member = archive.getmember(member_name)
        except KeyError as error:
            raise SourceDataError(f"archive member not found: {member_name}") from error
        if not member.isfile():
            raise SourceDataError(f"archive member is not a regular file: {member_name}")
        raw = archive.extractfile(member)
        if raw is None:
            raise SourceDataError(f"archive member cannot be read: {member_name}")
        reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise SourceDataError(
                f"unexpected CSV header: expected {EXPECTED_COLUMNS}, got {reader.fieldnames}"
            )

        previous_time: datetime | None = None
        for sample_index, row in enumerate(reader):
            if max_samples and sample_index >= max_samples:
                break
            if None in row:
                raise SourceDataError(f"row {sample_index} has extra columns")
            missing = [name for name in EXPECTED_COLUMNS if not (row.get(name) or "").strip()]
            if missing:
                raise SourceDataError(f"row {sample_index} has blank fields: {missing}")
            source_timestamp = row["timestamp"]
            source_time = parse_source_timestamp(source_timestamp)
            if previous_time is not None and source_time <= previous_time:
                raise SourceDataError(f"row {sample_index} timestamp is not strictly increasing")
            previous_time = source_time
            try:
                numeric = {name: int(row[name]) for name in NUMERIC_COLUMNS}
            except ValueError as error:
                raise SourceDataError(f"row {sample_index} has a non-integer sensor value") from error
            yield ImuSample(
                source_timestamp=source_timestamp,
                source_time=source_time,
                sample_index=sample_index,
                acc_x_mg=numeric["acc_x_mg"],
                acc_y_mg=numeric["acc_y_mg"],
                acc_z_mg=numeric["acc_z_mg"],
            )
