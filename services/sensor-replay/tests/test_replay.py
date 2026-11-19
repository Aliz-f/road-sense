from __future__ import annotations

import json
import threading
import unittest
import uuid
from datetime import datetime, timedelta, timezone

from sensor_replay.model import ImuSample
from sensor_replay.replay import batches, replay


def samples(count: int) -> list[ImuSample]:
    start = datetime(2026, 10, 19, 5, 51, 57, tzinfo=timezone.utc)
    return [
        ImuSample(
            source_timestamp=(start + timedelta(seconds=index)).isoformat().replace("+00:00", "Z"),
            source_time=start + timedelta(seconds=index),
            sample_index=index,
            acc_x_mg=index,
            acc_y_mg=2,
            acc_z_mg=1000,
        )
        for index in range(count)
    ]


class Publisher:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    def publish(self, topic: str, payload: bytes) -> None:
        self.messages.append({"topic": topic, "payload": json.loads(payload)})


class Clock:
    def __init__(self) -> None:
        self.value = 0.0
        self.waits: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def wait(self, delay: float) -> bool:
        self.waits.append(delay)
        self.value += delay
        return False


class ReplayTests(unittest.TestCase):
    def test_batches_are_bounded_and_partial_tail_is_kept(self) -> None:
        self.assertEqual([len(value) for value in batches(samples(5), 2)], [2, 2, 1])

    def test_replay_preserves_sequences_and_scales_source_time(self) -> None:
        publisher = Publisher()
        clock = Clock()
        messages, sample_count = replay(
            samples=samples(3),
            publisher=publisher,
            topic="roadsense/v1/imu/raw",
            run_id=str(uuid.uuid4()),
            session_id="session",
            sensor_id="sensor",
            source_archive_sha256="a" * 64,
            source_member="imu/bosch.csv",
            batch_size=1,
            max_payload_bytes=4096,
            replay_rate=2.0,
            stop_event=threading.Event(),
            monotonic=clock.monotonic,
            wait=clock.wait,
        )
        self.assertEqual((messages, sample_count), (3, 3))
        self.assertEqual(clock.waits, [0.5, 0.5])
        self.assertEqual(
            [message["payload"]["sequence_id"] for message in publisher.messages], [0, 1, 2]
        )
        self.assertEqual(
            [message["payload"]["samples"][0]["sample_index"] for message in publisher.messages],
            [0, 1, 2],
        )

    def test_stop_event_prevents_publication(self) -> None:
        stop = threading.Event()
        stop.set()
        publisher = Publisher()
        result = replay(
            samples=samples(1),
            publisher=publisher,
            topic="topic",
            run_id=str(uuid.uuid4()),
            session_id="session",
            sensor_id="sensor",
            source_archive_sha256="a" * 64,
            source_member="imu/bosch.csv",
            batch_size=1,
            max_payload_bytes=4096,
            replay_rate=0,
            stop_event=stop,
        )
        self.assertEqual(result, (0, 0))

    def test_shutdown_interrupts_source_time_wait(self) -> None:
        stop = threading.Event()
        publisher = Publisher()

        def interrupt_wait(delay: float) -> bool:
            self.assertGreater(delay, 0)
            stop.set()
            return True

        result = replay(
            samples=samples(2),
            publisher=publisher,
            topic="topic",
            run_id=str(uuid.uuid4()),
            session_id="session",
            sensor_id="sensor",
            source_archive_sha256="a" * 64,
            source_member="imu/bosch.csv",
            batch_size=1,
            max_payload_bytes=4096,
            replay_rate=1,
            stop_event=stop,
            monotonic=lambda: 0,
            wait=interrupt_wait,
        )
        self.assertEqual(result, (1, 1))
        self.assertEqual(len(publisher.messages), 1)
