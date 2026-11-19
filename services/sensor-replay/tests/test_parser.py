from __future__ import annotations

import hashlib
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from sensor_replay.parser import EXPECTED_COLUMNS, SourceDataError, iter_imu_samples


def write_archive(rows: list[list[str]], header=EXPECTED_COLUMNS) -> tuple[tempfile.TemporaryDirectory, Path, str]:
    temporary = tempfile.TemporaryDirectory()
    archive_path = Path(temporary.name) / "imu.tar"
    csv_text = ",".join(header) + "\n" + "\n".join(",".join(row) for row in rows) + "\n"
    data = csv_text.encode()
    with tarfile.open(archive_path, "w") as archive:
        info = tarfile.TarInfo("imu/bosch_imu.csv")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    return temporary, archive_path, digest


def row(timestamp: str, x: str = "1") -> list[str]:
    return [timestamp, x, "2", "1000", "4", "5", "6", "7", "8", "9", "10"]


class ParserTests(unittest.TestCase):
    def test_parses_verified_rows_and_preserves_source_values(self) -> None:
        temporary, path, digest = write_archive(
            [row("2026-10-19T05:51:57.052Z", "44"), row("2026-10-19T05:51:57.064Z", "43")]
        )
        self.addCleanup(temporary.cleanup)
        samples = list(iter_imu_samples(path, "imu/bosch_imu.csv", digest))
        self.assertEqual([sample.sample_index for sample in samples], [0, 1])
        self.assertEqual(samples[0].source_timestamp, "2026-10-19T05:51:57.052Z")
        self.assertEqual(samples[0].acc_x_mg, 44)

    def test_rejects_archive_hash_mismatch(self) -> None:
        temporary, path, _ = write_archive([row("2026-10-19T05:51:57.052Z")])
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(SourceDataError, "SHA-256 mismatch"):
            list(iter_imu_samples(path, "imu/bosch_imu.csv", "0" * 64))

    def test_rejects_header_drift(self) -> None:
        temporary, path, digest = write_archive(
            [row("2026-10-19T05:51:57.052Z")], header=EXPECTED_COLUMNS[:-1]
        )
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(SourceDataError, "unexpected CSV header"):
            list(iter_imu_samples(path, "imu/bosch_imu.csv", digest))

    def test_rejects_non_utc_and_non_increasing_timestamps(self) -> None:
        temporary, path, digest = write_archive([row("2026-10-19T05:51:57.052+03:00")])
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(SourceDataError, "not UTC RFC 3339"):
            list(iter_imu_samples(path, "imu/bosch_imu.csv", digest))

        temporary2, path2, digest2 = write_archive(
            [row("2026-10-19T05:51:57.052Z"), row("2026-10-19T05:51:57.052Z")]
        )
        self.addCleanup(temporary2.cleanup)
        with self.assertRaisesRegex(SourceDataError, "not strictly increasing"):
            list(iter_imu_samples(path2, "imu/bosch_imu.csv", digest2))

    def test_rejects_blank_and_non_integer_values(self) -> None:
        temporary, path, digest = write_archive([row("2026-10-19T05:51:57.052Z", "")])
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(SourceDataError, "blank fields"):
            list(iter_imu_samples(path, "imu/bosch_imu.csv", digest))

        temporary2, path2, digest2 = write_archive(
            [row("2026-10-19T05:51:57.052Z", "not-an-int")]
        )
        self.addCleanup(temporary2.cleanup)
        with self.assertRaisesRegex(SourceDataError, "non-integer"):
            list(iter_imu_samples(path2, "imu/bosch_imu.csv", digest2))

    def test_max_samples_bounds_source_iteration(self) -> None:
        temporary, path, digest = write_archive(
            [row("2026-10-19T05:51:57.052Z"), row("2026-10-19T05:51:57.064Z")]
        )
        self.addCleanup(temporary.cleanup)
        self.assertEqual(len(list(iter_imu_samples(path, "imu/bosch_imu.csv", digest, 1))), 1)
