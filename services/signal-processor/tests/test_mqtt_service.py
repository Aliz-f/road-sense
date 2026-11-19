from __future__ import annotations

import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from signal_processor.config import ProcessorConfig
from signal_processor.mqtt_service import MqttSignalProcessor, QueuedMessage


class BackpressureTests(unittest.TestCase):
    def test_full_small_queue_fails_closed_without_blocking_callback(self) -> None:
        config = ProcessorConfig(
            mqtt_host="mqtt-broker",
            mqtt_port=8883,
            mqtt_username="test-user",
            mqtt_password="test-password",
            mqtt_tls_ca_file=Path("/unused/ca.crt"),
            raw_topic="roadsense/v1/imu/raw",
            run_complete_topic="roadsense/v1/imu/run-complete",
            feature_topic="roadsense/v1/imu/features",
            client_id="test-processor",
            connect_timeout_seconds=1,
            publish_timeout_seconds=1,
            queue_capacity=1,
        )
        client = MagicMock()
        with patch("signal_processor.mqtt_service.mqtt.Client", return_value=client):
            stop_event = threading.Event()
            service = MqttSignalProcessor(config, stop_event)
        service.messages.put_nowait(
            QueuedMessage(
                topic=config.raw_topic,
                payload=b"first",
                message_id=1,
                qos=1,
            )
        )
        message = SimpleNamespace(
            topic=config.raw_topic,
            payload=b"overflow",
            mid=2,
            qos=1,
        )

        started = time.monotonic()
        service._on_message(None, None, message)
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.1)
        self.assertEqual(service.messages.qsize(), 1)
        self.assertIsNotNone(service.fatal_error)
        self.assertTrue(stop_event.is_set())
        client.ack.assert_not_called()


if __name__ == "__main__":
    unittest.main()
