from __future__ import annotations

import json
import queue
import ssl
import threading
from dataclasses import dataclass

import paho.mqtt.client as mqtt

from .config import AnalyzerConfig
from .events import emit, emit_error
from .registry import SessionRegistry
from .schema import parse_feature_message
from .storage import AnalyzerStore, ConflictingDataError


@dataclass(frozen=True, slots=True)
class QueuedMessage:
    payload: bytes
    message_id: int
    qos: int
    duplicate_delivery: bool


class MqttRoadAnalyzer:
    def __init__(
        self,
        config: AnalyzerConfig,
        registry: SessionRegistry,
        store: AnalyzerStore,
        stop_event: threading.Event,
    ) -> None:
        self.config = config
        self.registry = registry
        self.store = store
        self.stop_event = stop_event
        self.messages: queue.Queue[QueuedMessage] = queue.Queue(maxsize=config.queue_capacity)
        self.connected = threading.Event()
        self.subscribed = threading.Event()
        self.fatal_error: RuntimeError | None = None
        self._fatal_lock = threading.Lock()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=config.client_id,
            clean_session=False,
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(config.mqtt_username, config.mqtt_password)
        self.client.tls_set(ca_certs=str(config.mqtt_tls_ca_file), tls_version=ssl.PROTOCOL_TLS_CLIENT)
        self.client.reconnect_delay_set(min_delay=1, max_delay=5)
        self.client.manual_ack_set(True)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._on_message
        self._loop_started = False

    def _clear_ready(self) -> None:
        self.config.ready_file.unlink(missing_ok=True)

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        del userdata, flags, properties
        if reason_code != 0:
            self.connected.clear()
            self.subscribed.clear()
            self._clear_ready()
            emit("analyzer_connection_rejected", reason_code=str(reason_code))
            return
        self.connected.set()
        self.subscribed.clear()
        result, _ = client.subscribe(self.config.feature_topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            emit("analyzer_subscribe_failed", result=result)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        del client, userdata, disconnect_flags, properties
        self.connected.clear()
        self.subscribed.clear()
        self._clear_ready()
        if reason_code != 0 and not self.stop_event.is_set():
            emit("analyzer_disconnected", reason_code=str(reason_code))

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties) -> None:
        del client, userdata, mid, properties
        if any(code.is_failure for code in reason_codes):
            emit("analyzer_subscribe_rejected")
            return
        self.subscribed.set()
        self.config.ready_file.touch(mode=0o600, exist_ok=True)
        emit(
            "analyzer_ready",
            feature_topic=self.config.feature_topic,
            event_topic=self.config.event_topic,
            rule_version=self.config.rule_version,
            vibration_rms_threshold_mg=self.config.vibration_rms_threshold_mg,
        )

    def _on_message(self, client, userdata, message) -> None:
        del client, userdata
        queued = QueuedMessage(
            payload=bytes(message.payload),
            message_id=message.mid,
            qos=message.qos,
            duplicate_delivery=bool(message.dup),
        )
        try:
            self.messages.put_nowait(queued)
        except queue.Full:
            error = RuntimeError("analyzer queue overflowed despite broker inflight backpressure")
            with self._fatal_lock:
                if self.fatal_error is None:
                    self.fatal_error = error
                    emit_error("analyzer_queue_overflow", error, queue_capacity=self.config.queue_capacity)
            self.stop_event.set()

    def start(self) -> None:
        self._clear_ready()
        result = self.client.connect(self.config.mqtt_host, self.config.mqtt_port, keepalive=30)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT connect returned {result}")
        self.client.loop_start()
        self._loop_started = True
        if not self.subscribed.wait(self.config.connect_timeout_seconds):
            raise TimeoutError("timed out waiting for analyzer MQTT subscription")

    def _ack(self, message: QueuedMessage) -> None:
        result = self.client.ack(message.message_id, message.qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT message acknowledgement returned {result}")

    def _publish_event(self, event_payload: dict[str, object]) -> None:
        if not self.connected.wait(self.config.publish_timeout_seconds):
            raise TimeoutError("timed out waiting for MQTT reconnection")
        encoded = json.dumps(event_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        result = self.client.publish(self.config.event_topic, payload=encoded, qos=1, retain=False)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT event publish returned {result.rc}")
        result.wait_for_publish(timeout=self.config.publish_timeout_seconds)
        if not result.is_published():
            raise TimeoutError("timed out waiting for event QoS 1 acknowledgement")
        emit(
            "event_published",
            event_id=event_payload["event_id"],
            run_id=event_payload["run_id"],
            window_index=event_payload["window_index"],
        )

    def _handle(self, message: QueuedMessage) -> None:
        try:
            feature = parse_feature_message(message.payload)
            session = self.registry.match(feature)
        except ValueError as error:
            emit_error("feature_rejected", error, message_id=message.message_id)
            self._ack(message)
            return
        try:
            result = self.store.store_feature(feature, session)
        except ConflictingDataError as error:
            emit_error(
                "feature_conflict",
                error,
                message_id=message.message_id,
                run_id=feature.run_id,
                window_index=feature.window_index,
            )
            self._ack(message)
            return
        if result.event_payload is not None:
            self._publish_event(result.event_payload)
        emit(
            "feature_duplicate" if result.duplicate else "feature_stored",
            run_id=feature.run_id,
            window_index=feature.window_index,
            mqtt_duplicate=message.duplicate_delivery,
            event_detected=result.event_payload is not None,
        )
        self._ack(message)

    def run(self) -> None:
        while not self.stop_event.is_set() or not self.messages.empty():
            try:
                message = self.messages.get(timeout=0.2)
            except queue.Empty:
                continue
            self._handle(message)
        if self.fatal_error is not None:
            raise self.fatal_error

    def close(self) -> None:
        self._clear_ready()
        try:
            if self.connected.is_set():
                self.client.disconnect()
        finally:
            if self._loop_started:
                self.client.loop_stop()
                self._loop_started = False
            self.connected.clear()
            self.subscribed.clear()
