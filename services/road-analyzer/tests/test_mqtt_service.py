from __future__ import annotations

import queue
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import encoded_feature
from road_analyzer.config import AnalyzerConfig
from road_analyzer.model import StoreResult
from road_analyzer.mqtt_service import MqttRoadAnalyzer, QueuedMessage
from road_analyzer.registry import SessionRegistry
from road_analyzer.storage import ConflictingDataError


class PublishResult:
    rc = 0

    def wait_for_publish(self, timeout: float) -> None:
        del timeout

    def is_published(self) -> bool:
        return True


class FakeClient:
    def __init__(self, *args, **kwargs) -> None:
        del args, kwargs
        self.acks: list[tuple[int, int]] = []
        self.published: list[tuple[str, bytes, int, bool]] = []

    def username_pw_set(self, *args) -> None:
        del args

    def tls_set(self, *args, **kwargs) -> None:
        del args, kwargs

    def reconnect_delay_set(self, *args, **kwargs) -> None:
        del args, kwargs

    def manual_ack_set(self, *args) -> None:
        del args

    def ack(self, message_id: int, qos: int) -> int:
        self.acks.append((message_id, qos))
        return 0

    def publish(self, topic: str, payload: bytes, qos: int, retain: bool) -> PublishResult:
        self.published.append((topic, payload, qos, retain))
        return PublishResult()


class FakeStore:
    def __init__(self, result: StoreResult | Exception) -> None:
        self.result = result

    def store_feature(self, feature, session) -> StoreResult:
        del feature, session
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def config(queue_capacity: int = 1) -> AnalyzerConfig:
    return AnalyzerConfig(
        mqtt_host="mqtt-broker", mqtt_port=8883, mqtt_username="user",
        mqtt_password="password", mqtt_tls_ca_file=Path("/ca.crt"),
        feature_topic="roadsense/v1/imu/features", event_topic="roadsense/v1/events",
        client_id="analyzer-test", connect_timeout_seconds=1,
        publish_timeout_seconds=1, queue_capacity=queue_capacity,
        postgres_host="postgres", postgres_port=5432, postgres_db="roadsense",
        postgres_user="roadsense", postgres_password="password",
        postgres_connect_timeout_seconds=1, postgres_connect_retries=1,
        session_registry_file=Path("/app/session-registry.json"),
        vibration_rms_threshold_mg=100.0, rule_version="rule-v1",
        ready_file=Path("/tmp/analyzer-test-ready"),
    )


class MqttServiceTests(unittest.TestCase):
    def build(self, result: StoreResult | Exception, capacity: int = 1) -> MqttRoadAnalyzer:
        with patch("road_analyzer.mqtt_service.mqtt.Client", FakeClient):
            return MqttRoadAnalyzer(
                config(capacity),
                SessionRegistry.load(Path("/app/session-registry.json")),
                FakeStore(result),
                threading.Event(),
            )

    def test_full_queue_fails_closed_without_replacing_message(self) -> None:
        service = self.build(StoreResult(False, None))
        original = QueuedMessage(b"first", 1, 1, False)
        service.messages.put_nowait(original)
        incoming = type("Message", (), {"payload": b"second", "mid": 2, "qos": 1, "dup": False})()
        service._on_message(None, None, incoming)
        self.assertTrue(service.stop_event.is_set())
        self.assertIsInstance(service.fatal_error, RuntimeError)
        self.assertEqual(service.messages.get_nowait(), original)
        with self.assertRaises(queue.Empty):
            service.messages.get_nowait()

    def test_invalid_feature_is_acknowledged_and_not_stored(self) -> None:
        service = self.build(StoreResult(False, None))
        message = QueuedMessage(b"not-json", 7, 1, False)
        service._handle(message)
        self.assertEqual(service.client.acks, [(7, 1)])
        self.assertEqual(service.client.published, [])

    def test_conflicting_feature_is_acknowledged_without_publish(self) -> None:
        service = self.build(ConflictingDataError("conflict"))
        service._handle(QueuedMessage(encoded_feature(), 8, 1, True))
        self.assertEqual(service.client.acks, [(8, 1)])
        self.assertEqual(service.client.published, [])

    def test_stored_event_is_published_before_acknowledgement(self) -> None:
        event = {"event_id": "id", "run_id": "run", "window_index": 0}
        service = self.build(StoreResult(False, event))
        service.connected.set()
        service._handle(QueuedMessage(encoded_feature(), 9, 1, False))
        self.assertEqual(service.client.published[0][0], "roadsense/v1/events")
        self.assertEqual(service.client.acks, [(9, 1)])


if __name__ == "__main__":
    unittest.main()
