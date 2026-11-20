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
from .state import JournalRecord, ProcessorState


@dataclass(frozen=True, slots=True)
class QueuedMessage:
    topic: str
    payload: bytes
    message_id: int
    qos: int


class MqttSignalProcessor:
    def __init__(self, config: ProcessorConfig, stop_event: threading.Event) -> None:
        self.config = config
        self.stop_event = stop_event
        self.engine = SignalEngine()
        self.state = ProcessorState(
            config.state_file, config.rejected_tombstone_limit
        )
        self.messages: queue.Queue[QueuedMessage] = queue.Queue(
            maxsize=config.queue_capacity
        )
        self.connected = threading.Event()
        self.subscribed = threading.Event()
        self._initial_recovery_complete = threading.Event()
        self._readiness_lock = threading.Lock()
        self.fatal_error: RuntimeError | None = None
        self._fatal_lock = threading.Lock()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=config.client_id,
            # A stable client ID plus a persistent MQTT 3.1.1 session lets the
            # broker queue QoS 1 raw/control messages while this process is
            # disconnected. The broker-side persistence is configured too.
            clean_session=False,
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

    def _sync_readiness_locked(self) -> bool:
        ready = (
            self.connected.is_set()
            and self.subscribed.is_set()
            and self._initial_recovery_complete.is_set()
        )
        was_ready = self.config.ready_file.exists()
        if ready:
            self.config.ready_file.touch(mode=0o600, exist_ok=True)
        else:
            self.config.ready_file.unlink(missing_ok=True)
        return ready and not was_ready

    def _sync_readiness(self) -> bool:
        with self._readiness_lock:
            return self._sync_readiness_locked()

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        del userdata, flags, properties
        if reason_code != 0:
            with self._readiness_lock:
                self.connected.clear()
                self.subscribed.clear()
                self._sync_readiness_locked()
            emit("processor_connection_rejected", reason_code=str(reason_code))
            return
        with self._readiness_lock:
            self.connected.set()
            self.subscribed.clear()
            self._sync_readiness_locked()
        result, _ = client.subscribe(
            [
                (self.config.raw_topic, 1),
                (self.config.run_complete_topic, 1),
            ]
        )
        if result != mqtt.MQTT_ERR_SUCCESS:
            emit("processor_subscribe_failed", result=result)

    def _on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties
    ) -> None:
        del client, userdata, disconnect_flags, properties
        with self._readiness_lock:
            self.connected.clear()
            self.subscribed.clear()
            self._sync_readiness_locked()
        if reason_code != 0 and not self.stop_event.is_set():
            emit("processor_disconnected", reason_code=str(reason_code))

    def _on_subscribe(self, client, userdata, mid, reason_codes, properties) -> None:
        del client, userdata, mid, properties
        if any(code.is_failure for code in reason_codes):
            emit("processor_subscribe_rejected")
            return
        with self._readiness_lock:
            self.subscribed.set()
            became_ready = self._sync_readiness_locked()
        if became_ready:
            emit(
                "processor_ready",
                raw_topic=self.config.raw_topic,
                run_complete_topic=self.config.run_complete_topic,
            )

    def _on_message(self, client, userdata, message) -> None:
        del client, userdata
        queued = QueuedMessage(
            topic=message.topic,
            payload=bytes(message.payload),
            message_id=message.mid,
            qos=message.qos,
        )
        try:
            self.messages.put_nowait(queued)
        except queue.Full:
            error = RuntimeError(
                "processor queue overflowed despite broker inflight backpressure"
            )
            with self._fatal_lock:
                if self.fatal_error is None:
                    self.fatal_error = error
                    emit_error(
                        "processor_queue_overflow",
                        error,
                        queue_capacity=self.config.queue_capacity,
                    )
            # Fail closed without blocking Paho's network thread. The message
            # is deliberately not acknowledged and the service exits nonzero.
            self.stop_event.set()

    def start(self) -> None:
        self._sync_readiness()
        result = self.client.connect(
            self.config.mqtt_host, self.config.mqtt_port, keepalive=30
        )
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT connect returned {result}")
        self.client.loop_start()
        self._loop_started = True
        if not self.subscribed.wait(self.config.connect_timeout_seconds):
            raise TimeoutError("timed out waiting for MQTT subscription")
        self._recover()
        with self._readiness_lock:
            self._initial_recovery_complete.set()
            became_ready = self._sync_readiness_locked()
        if became_ready:
            emit(
                "processor_ready",
                raw_topic=self.config.raw_topic,
                run_complete_topic=self.config.run_complete_topic,
            )

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

    def _process_record(self, record: JournalRecord) -> list[dict[str, object]]:
        if record.topic == self.config.raw_topic:
            return self.engine.process_message(record.payload)
        if record.topic == self.config.run_complete_topic:
            return self.engine.complete_run(record.payload)
        raise ValueError(f"unexpected MQTT topic: {record.topic}")

    def _recover(self) -> None:
        records = self.state.recoverable()
        for record in records:
            try:
                features = self._process_record(record)
                for feature in features:
                    self._publish(feature)
            except ValueError as error:
                self.state.set_status(record.record_id, "rejected")
                emit_error(
                    "processor_recovery_record_rejected",
                    error,
                    record_id=record.record_id,
                )
                continue
            self.state.set_status(record.record_id, "accepted")
        self.state.prune_completed(self.engine.completed_run_ids())
        emit("processor_state_recovered", journal_records=len(records))

    def _handle(self, message: QueuedMessage) -> None:
        record = self.state.journal(message.topic, message.payload)
        if record.status == "rejected":
            result = self.client.ack(message.message_id, message.qos)
            if result != mqtt.MQTT_ERR_SUCCESS:
                raise ConnectionError(
                    f"MQTT message acknowledgement returned {result}"
                )
            return
        event = (
            "raw_message_rejected"
            if message.topic == self.config.raw_topic
            else "run_complete_rejected"
        )
        try:
            features = self._process_record(record)
            for feature in features:
                self._publish(feature)
        except ValueError as error:
            self.state.set_status(record.record_id, "rejected")
            emit_error(event, error, message_id=message.message_id)
        else:
            self.state.set_status(record.record_id, "accepted")
            self.state.prune_completed(self.engine.completed_run_ids())
        result = self.client.ack(message.message_id, message.qos)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT message acknowledgement returned {result}")

    def run(self) -> None:
        while not self.stop_event.is_set() or not self.messages.empty():
            try:
                message = self.messages.get(timeout=0.2)
            except queue.Empty:
                continue
            self._handle(message)
        if self.fatal_error is not None:
            raise self.fatal_error
        # Do not finalize open windows on service shutdown. Their acknowledged
        # input is durably journaled and must resume after restart; emitting an
        # incomplete feature here could conflict with the later complete one.

    def close(self) -> None:
        was_connected = self.connected.is_set()
        with self._readiness_lock:
            self.connected.clear()
            self.subscribed.clear()
            self._sync_readiness_locked()
        try:
            if was_connected:
                self.client.disconnect()
        finally:
            if self._loop_started:
                self.client.loop_stop()
                self._loop_started = False
            self.state.close()
