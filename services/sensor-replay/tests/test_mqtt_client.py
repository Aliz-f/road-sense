from __future__ import annotations

import threading
import unittest
from unittest.mock import MagicMock, patch

import paho.mqtt.client as mqtt

from sensor_replay.mqtt_client import MqttPublisher, retry_call


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


class PublisherReconnectTests(unittest.TestCase):
    def make_publisher(self, client: MagicMock) -> MqttPublisher:
        with patch("sensor_replay.mqtt_client.mqtt.Client", return_value=client):
            return MqttPublisher(
                host="mqtt-broker",
                port=8883,
                username="test-user",
                password="test-password",
                ca_file="/run/roadsense/mqtt/ca.crt",
                run_id="fd1c9635-f818-42f3-a720-e4991f13ff69",
                connect_retries=2,
                connect_timeout_seconds=0.01,
                stop_event=threading.Event(),
            )

    def test_concurrent_start_calls_only_connect_client_once(self) -> None:
        client = MagicMock()
        client.connect.return_value = mqtt.MQTT_ERR_SUCCESS
        publisher = self.make_publisher(client)
        client.loop_start.side_effect = publisher.connected.set
        failures: list[BaseException] = []

        def start() -> None:
            try:
                publisher.start()
            except BaseException as error:
                failures.append(error)

        workers = [threading.Thread(target=start) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()

        self.assertEqual(failures, [])
        client.connect.assert_called_once_with("mqtt-broker", 8883, keepalive=30)
        client.loop_start.assert_called_once_with()

    def test_publish_does_not_compete_with_network_loop_reconnect(self) -> None:
        client = MagicMock()
        publisher = self.make_publisher(client)

        with self.assertRaisesRegex(ConnectionError, "after 2 attempts"):
            publisher.publish("roadsense/v1/imu/raw", b"payload")

        client.connect.assert_not_called()
        client.publish.assert_not_called()
