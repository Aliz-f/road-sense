from __future__ import annotations

import ssl
import threading
from collections.abc import Callable

import paho.mqtt.client as mqtt

from .events import emit


def retry_call(
    operation: Callable[[], None],
    *,
    attempts: int,
    stop_event: threading.Event,
    delay_seconds: float,
) -> int:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        if stop_event.is_set():
            raise InterruptedError("shutdown requested during MQTT connection")
        try:
            operation()
            return attempt
        except Exception as error:  # connection exceptions vary by platform
            last_error = error
            if attempt == attempts or stop_event.wait(delay_seconds):
                break
    if last_error is None:
        raise ConnectionError("MQTT connection did not run")
    raise ConnectionError(f"MQTT connection failed after {attempts} attempts") from last_error


class MqttPublisher:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        ca_file: str,
        run_id: str,
        connect_retries: int,
        connect_timeout_seconds: float,
        stop_event: threading.Event,
    ) -> None:
        self.host = host
        self.port = port
        self.connect_retries = connect_retries
        self.connect_timeout_seconds = connect_timeout_seconds
        self.stop_event = stop_event
        self.connected = threading.Event()
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"roadsense-replay-{run_id}",
            clean_session=True,
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(username, password)
        self.client.tls_set(ca_certs=ca_file, tls_version=ssl.PROTOCOL_TLS_CLIENT)
        self.client.reconnect_delay_set(min_delay=1, max_delay=5)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._loop_started = False

    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        del client, userdata, flags, properties
        if reason_code == 0:
            self.connected.set()
        else:
            self.connected.clear()

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        del client, userdata, disconnect_flags, properties
        self.connected.clear()
        if reason_code != 0 and not self.stop_event.is_set():
            emit("mqtt_disconnected", reason_code=str(reason_code))

    def _connect_once(self) -> None:
        self.connected.clear()
        result = self.client.connect(self.host, self.port, keepalive=30)
        if result != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT connect returned {result}")
        if not self._loop_started:
            self.client.loop_start()
            self._loop_started = True
        if not self.connected.wait(self.connect_timeout_seconds):
            raise TimeoutError("timed out waiting for MQTT CONNACK")

    def start(self) -> None:
        attempt = retry_call(
            self._connect_once,
            attempts=self.connect_retries,
            stop_event=self.stop_event,
            delay_seconds=1,
        )
        emit("mqtt_connected", host=self.host, port=self.port, attempt=attempt, tls=True)

    def publish(self, topic: str, payload: bytes) -> None:
        if not self.connected.wait(self.connect_timeout_seconds):
            retry_call(
                self._connect_once,
                attempts=self.connect_retries,
                stop_event=self.stop_event,
                delay_seconds=1,
            )
        result = self.client.publish(topic, payload=payload, qos=1, retain=False)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise ConnectionError(f"MQTT publish returned {result.rc}")
        result.wait_for_publish(timeout=self.connect_timeout_seconds)
        if not result.is_published():
            raise TimeoutError("timed out waiting for MQTT QoS 1 acknowledgement")

    def close(self) -> None:
        try:
            if self.connected.is_set():
                self.client.disconnect()
        finally:
            if self._loop_started:
                self.client.loop_stop()
                self._loop_started = False
            self.connected.clear()
