from __future__ import annotations

import threading
import time
import unittest
import tempfile
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
            ready_file=Path(tempfile.gettempdir()) / "processor-test-ready",
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

    def test_uses_stable_persistent_session_for_offline_qos1_recovery(self) -> None:
        config = ProcessorConfig(
            mqtt_host="mqtt-broker",
            mqtt_port=8883,
            mqtt_username="test-user",
            mqtt_password="test-password",
            mqtt_tls_ca_file=Path("/unused/ca.crt"),
            raw_topic="roadsense/v1/imu/raw",
            run_complete_topic="roadsense/v1/imu/run-complete",
            feature_topic="roadsense/v1/imu/features",
            client_id="stable-processor-id",
            connect_timeout_seconds=1,
            publish_timeout_seconds=1,
            queue_capacity=1,
            ready_file=Path(tempfile.gettempdir()) / "processor-session-test-ready",
        )
        client = MagicMock()
        client.subscribe.return_value = (0, 1)
        with patch("signal_processor.mqtt_service.mqtt.Client", return_value=client) as factory:
            service = MqttSignalProcessor(config, threading.Event())

        self.assertEqual(factory.call_args.kwargs["client_id"], "stable-processor-id")
        self.assertFalse(factory.call_args.kwargs["clean_session"])
        service._on_connect(
            client,
            None,
            SimpleNamespace(session_present=True),
            0,
            None,
        )
        client.subscribe.assert_called_once_with(
            [(config.raw_topic, 1), (config.run_complete_topic, 1)]
        )

    def test_readiness_is_cleared_when_processor_disconnects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            config = ProcessorConfig(
                mqtt_host="mqtt-broker", mqtt_port=8883,
                mqtt_username="user", mqtt_password="password",
                mqtt_tls_ca_file=Path("/unused/ca.crt"), raw_topic="raw",
                run_complete_topic="complete", feature_topic="features",
                client_id="stable", connect_timeout_seconds=1,
                publish_timeout_seconds=1, queue_capacity=1,
                ready_file=Path(temp) / "ready",
            )
            client = MagicMock()
            with patch("signal_processor.mqtt_service.mqtt.Client", return_value=client):
                service = MqttSignalProcessor(config, threading.Event())
            config.ready_file.touch()
            service._on_disconnect(client, None, None, 1, None)
            self.assertFalse(config.ready_file.exists())


if __name__ == "__main__":
    unittest.main()
