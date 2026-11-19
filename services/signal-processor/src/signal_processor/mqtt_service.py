from __future__ import annotations

import json
import queue
import ssl
import threading
from dataclasses import dataclass

import paho.mqtt.client as mqtt

from .config import ProcessorConfig
from .events import emit, emit_error
from .processor import SignalEngine


@dataclass(frozen=True, slots=True)
class QueuedMessage:
    payload: bytes
    message_id: int
    qos: int


class MqttSignalProcessor:
    def __init__(self, config: ProcessorConfig, stop_event: threading.Event) -> None:
        self.config = config
        self.stop_event = stop_event
        self.engine = SignalEngine()
        self.messages: queue.Queue[QueuedMessage] = queue.Queue(
            maxsize=config.queue_capacity
        )
        self.connected = threading.Event()
        self.subscribed = threading.Event()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=config.client_id,
            clean_session=True,
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(config.mqtt_username, config.mqtt_password)
        self.client.tls_set(
            ca_certs=str(config.mqtt_tls_ca_file),
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        self.client.reconnect_delay_set(min_delay=1, max_delay=5)
        self.client.manual_ack_set(True)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._on_message
        self._loop_started = False

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        del userdata, flags, properties
        if reason_code != 0:
            self.connected.clear()
            self.subscribed.clear()
            emit("processor_connection_rejected", reason_code=str(reason_code))
            return
        self.connected.set()
        self.subscribed.clear()
        result, _ = client.subscribe(self.config.raw_topic, qos=1)
        if result != mqtt.MQTT_ERR_SUCCESS:
            emit("processor_subscribe_failed", result=result)

    def _on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties
    ) -> None:
        del client, userdata, disconnect_flags, properties
        self.connected.clear()
        self.subscribed.clear()
        if reason_code != 0 and not self.stop_event.is_set():
            emit("processor_disconnected", reason_code=str(reason_code))

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties) -> None:
        del client, userdata, mid, properties
        if any(code.is_failure for code in reason_codes):
            emit("processor_subscribe_rejected")
            return
        self.subscribed.set()
        emit("processor_ready", raw_topic=self.config.raw_topic)

    def _on_message(self, client, userdata, message) -> None:
        del client, userdata
        queued = QueuedMessage(
            payload=bytes(message.payload),
            message_id=message.mid,
            qos=message.qos,
        )
        # Blocking here applies bounded backpressure to Paho's network thread;
        # returning without queueing would leave an unacknowledged message
        # stranded on an otherwise healthy connection.
        self.messages.put(queued)

    def start(self) -> None:
        result = self.client.connect(
            self.config.mqtt_host, self.config.mqtt_port, keepalive=30
        )
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT connect returned {result}")
        self.client.loop_start()
        self._loop_started = True
        if not self.subscribed.wait(self.config.connect_timeout_seconds):
            raise TimeoutError("timed out waiting for MQTT subscription")

    def _publish(self, feature: dict[str, object]) -> None:
        if not self.connected.wait(self.config.publish_timeout_seconds):
            raise TimeoutError("timed out waiting for MQTT reconnection")
        encoded = json.dumps(feature, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        result = self.client.publish(
            self.config.feature_topic, payload=encoded, qos=1, retain=False
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT feature publish returned {result.rc}")
        result.wait_for_publish(timeout=self.config.publish_timeout_seconds)
        if not result.is_published():
            raise TimeoutError("timed out waiting for feature QoS 1 acknowledgement")
        emit(
            "feature_published",
            run_id=feature["run_id"],
            window_index=feature["window_index"],
            sample_count=feature["sample_count"],
            quality_flags=feature["quality_flags"],
        )

    def _handle(self, message: QueuedMessage) -> None:
        try:
            features = self.engine.process_message(message.payload)
            for feature in features:
                self._publish(feature)
        except ValueError as error:
            emit_error("raw_message_rejected", error, message_id=message.message_id)
        result = self.client.ack(message.message_id, message.qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT raw acknowledgement returned {result}")

    def run(self) -> None:
        while not self.stop_event.is_set() or not self.messages.empty():
            try:
                message = self.messages.get(timeout=0.2)
            except queue.Empty:
                continue
            self._handle(message)
        for feature in self.engine.finalize_all():
            self._publish(feature)

    def close(self) -> None:
        try:
            if self.connected.is_set():
                self.client.disconnect()
        finally:
            if self._loop_started:
                self.client.loop_stop()
                self._loop_started = False
            self.connected.clear()
            self.subscribed.clear()
