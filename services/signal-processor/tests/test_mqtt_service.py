from __future__ import annotations

import json
import threading
import time
import unittest
import tempfile
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from signal_processor.config import ProcessorConfig
from signal_processor.mqtt_service import MqttSignalProcessor, QueuedMessage


class BackpressureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.services: list[MqttSignalProcessor] = []

    def tearDown(self) -> None:
        for service in self.services:
            service.close()
        self.temp.cleanup()

    def state_file(self, name: str) -> Path:
        return Path(self.temp.name) / f"{name}.sqlite3"

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
            ready_file=Path(self.temp.name) / "processor-test-ready",
            state_file=self.state_file("overflow"),
        )
        client = MagicMock()
        with patch("signal_processor.mqtt_service.mqtt.Client", return_value=client):
            stop_event = threading.Event()
            service = MqttSignalProcessor(config, stop_event)
            self.services.append(service)
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
            ready_file=Path(self.temp.name) / "processor-session-test-ready",
            state_file=self.state_file("session"),
        )
        client = MagicMock()
        client.subscribe.return_value = (0, 1)
        with patch("signal_processor.mqtt_service.mqtt.Client", return_value=client) as factory:
            service = MqttSignalProcessor(config, threading.Event())
            self.services.append(service)

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
                state_file=Path(temp) / "state.sqlite3",
            )
            client = MagicMock()
            with patch("signal_processor.mqtt_service.mqtt.Client", return_value=client):
                service = MqttSignalProcessor(config, threading.Event())
                self.services.append(service)
            config.ready_file.touch()
            service._on_disconnect(client, None, None, 1, None)
            self.assertFalse(config.ready_file.exists())

    def test_disconnect_during_recovery_cannot_publish_readiness(self) -> None:
        config = ProcessorConfig(
            mqtt_host="mqtt-broker", mqtt_port=8883,
            mqtt_username="user", mqtt_password="password",
            mqtt_tls_ca_file=Path("/unused/ca.crt"), raw_topic="raw",
            run_complete_topic="complete", feature_topic="features",
            client_id="stable", connect_timeout_seconds=1,
            publish_timeout_seconds=1, queue_capacity=1,
            ready_file=Path(self.temp.name) / "recovery-race-ready",
            state_file=self.state_file("recovery-race"),
        )
        client = MagicMock()
        client.connect.return_value = 0
        client.subscribe.return_value = (0, 1)
        with patch("signal_processor.mqtt_service.mqtt.Client", return_value=client):
            service = MqttSignalProcessor(config, threading.Event())
            self.services.append(service)
        service.connected.set()
        service.subscribed.set()

        def disconnect_while_recovering() -> None:
            service._on_disconnect(client, None, None, 1, None)

        with patch.object(service, "_recover", side_effect=disconnect_while_recovering):
            service.start()

        self.assertTrue(service._initial_recovery_complete.is_set())
        self.assertFalse(service.connected.is_set())
        self.assertFalse(config.ready_file.exists())

        service._on_connect(client, None, None, 0, None)
        service._on_subscribe(
            client,
            None,
            1,
            [SimpleNamespace(is_failure=False)],
            None,
        )
        self.assertTrue(config.ready_file.exists())

    def test_crash_recovery_preserves_anchor_window_index_and_samples(self) -> None:
        run_id = str(uuid.uuid4())

        def batch(sequence_id: int, samples: list[dict[str, object]]) -> bytes:
            return json.dumps(
                {
                    "schema_version": 1,
                    "run_id": run_id,
                    "session_id": "session",
                    "sensor_id": "bosch-xdk-110",
                    "sequence_id": sequence_id,
                    "source_archive_sha256": "a" * 64,
                    "source_member": "imu/bosch_imu.csv",
                    "acceleration_unit": "mg",
                    "samples": samples,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()

        def sample(index: int, timestamp: str) -> dict[str, object]:
            return {
                "source_timestamp": timestamp,
                "sample_index": index,
                "acc_x_mg": 100 + index,
                "acc_y_mg": 0,
                "acc_z_mg": 1000,
            }

        state_file = self.state_file("crash-recovery")

        def config() -> ProcessorConfig:
            return ProcessorConfig(
                mqtt_host="mqtt-broker", mqtt_port=8883,
                mqtt_username="user", mqtt_password="password",
                mqtt_tls_ca_file=Path("/unused/ca.crt"), raw_topic="raw",
                run_complete_topic="complete", feature_topic="features",
                client_id="stable", connect_timeout_seconds=1,
                publish_timeout_seconds=1, queue_capacity=4,
                ready_file=Path(self.temp.name) / "recovery-ready",
                state_file=state_file,
            )

        first_client = MagicMock()
        first_client.ack.return_value = 0
        with patch("signal_processor.mqtt_service.mqtt.Client", return_value=first_client):
            first = MqttSignalProcessor(config(), threading.Event())
        first._handle(
            QueuedMessage(
                "raw",
                batch(
                    0,
                    [
                        sample(0, "2026-10-19T10:00:00.000Z"),
                        sample(1, "2026-10-19T10:00:00.012Z"),
                    ],
                ),
                1,
                1,
            )
        )
        self.assertEqual(first_client.ack.call_args.args, (1, 1))
        first.close()

        second_client = MagicMock()
        second_client.ack.return_value = 0
        with patch("signal_processor.mqtt_service.mqtt.Client", return_value=second_client):
            recovered = MqttSignalProcessor(config(), threading.Event())
        self.services.append(recovered)
        recovered._recover()
        published: list[dict[str, object]] = []
        recovered._publish = published.append  # type: ignore[method-assign]
        recovered._handle(
            QueuedMessage(
                "raw",
                batch(1, [sample(2, "2026-10-19T10:00:01.008Z")]),
                2,
                1,
            )
        )

        self.assertEqual(len(published), 1)
        self.assertEqual(published[0]["window_index"], 0)
        self.assertEqual(published[0]["sample_count"], 2)
        self.assertEqual(published[0]["source_start"], "2026-10-19T10:00:00.000Z")
        self.assertEqual(second_client.ack.call_args.args, (2, 1))

    def test_shutdown_does_not_finalize_a_recoverable_open_window(self) -> None:
        config = ProcessorConfig(
            mqtt_host="mqtt-broker", mqtt_port=8883,
            mqtt_username="user", mqtt_password="password",
            mqtt_tls_ca_file=Path("/unused/ca.crt"), raw_topic="raw",
            run_complete_topic="complete", feature_topic="features",
            client_id="stable", connect_timeout_seconds=1,
            publish_timeout_seconds=1, queue_capacity=1,
            ready_file=Path(self.temp.name) / "shutdown-ready",
            state_file=self.state_file("shutdown"),
        )
        with patch("signal_processor.mqtt_service.mqtt.Client", return_value=MagicMock()):
            service = MqttSignalProcessor(config, threading.Event())
        self.services.append(service)
        service.stop_event.set()
        service.engine.finalize_all = MagicMock(return_value=[{"window_index": 0}])
        service._publish = MagicMock()  # type: ignore[method-assign]

        service.run()

        service.engine.finalize_all.assert_not_called()
        service._publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
