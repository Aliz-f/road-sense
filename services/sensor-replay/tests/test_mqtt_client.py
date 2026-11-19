from __future__ import annotations

import threading
import unittest

from sensor_replay.mqtt_client import retry_call


class RetryTests(unittest.TestCase):
    def test_retries_initial_connection_until_success(self) -> None:
        attempts = 0

        def connect() -> None:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise OSError("broker unavailable")

        used_attempt = retry_call(
            connect,
            attempts=4,
            stop_event=threading.Event(),
            delay_seconds=0,
        )
        self.assertEqual(used_attempt, 3)
        self.assertEqual(attempts, 3)

    def test_reconnect_exhaustion_is_reported(self) -> None:
        def connect() -> None:
            raise OSError("still unavailable")

        with self.assertRaisesRegex(ConnectionError, "after 2 attempts"):
            retry_call(
                connect,
                attempts=2,
                stop_event=threading.Event(),
                delay_seconds=0,
            )

    def test_shutdown_cancels_reconnect(self) -> None:
        stop = threading.Event()
        stop.set()
        with self.assertRaises(InterruptedError):
            retry_call(lambda: None, attempts=2, stop_event=stop, delay_seconds=0)
