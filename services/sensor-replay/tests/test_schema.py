from __future__ import annotations

import json
import unittest
import uuid
from datetime import datetime, timezone

from sensor_replay.model import ImuSample
from sensor_replay.schema import build_raw_payload, encode_payload, validate_raw_payload


def sample(index: int, millisecond: int) -> ImuSample:
    value = f"2026-10-19T05:51:57.{millisecond:03d}Z"
    return ImuSample(value, datetime.fromisoformat(value[:-1] + "+00:00"), index, 1, 2, 1000)


class SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.run_id = str(uuid.uuid4())
        self.payload = build_raw_payload(
            run_id=self.run_id,
            session_id="bumpy-gravel-20261019",
            sensor_id="bosch-xdk-110",
            sequence_id=0,
            source_archive_sha256="a" * 64,
            source_member="imu/bosch_imu.csv",
            samples=[sample(0, 52), sample(1, 64)],
        )

    def test_builds_contract_payload(self) -> None:
        validate_raw_payload(self.payload)
        self.assertEqual(self.payload["acceleration_unit"], "mg")
        self.assertEqual(self.payload["samples"][1]["sample_index"], 1)

    def test_rejects_invalid_run_id_and_sequence(self) -> None:
        bad = dict(self.payload, run_id="not-a-uuid")
        with self.assertRaisesRegex(ValueError, "run_id"):
            validate_raw_payload(bad)
        bad = dict(self.payload, sequence_id=-1)
        with self.assertRaisesRegex(ValueError, "sequence_id"):
            validate_raw_payload(bad)

    def test_rejects_non_contiguous_samples(self) -> None:
        bad = json.loads(json.dumps(self.payload))
        bad["samples"][1]["sample_index"] = 3
        with self.assertRaisesRegex(ValueError, "contiguous"):
            validate_raw_payload(bad)

    def test_payload_byte_limit_is_enforced(self) -> None:
        encoded = encode_payload(self.payload, 4096)
        self.assertLess(len(encoded), 4096)
        with self.assertRaisesRegex(ValueError, "limit"):
            encode_payload(self.payload, 10)
