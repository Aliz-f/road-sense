from __future__ import annotations

import json
import os
import ssl
import sys
import threading
import uuid

import paho.mqtt.client as mqtt

from .schema import validate_raw_payload


def main() -> int:
    host = os.environ["MQTT_HOST"]
    port = int(os.environ.get("MQTT_PORT", "8883"))
    username = os.environ["MQTT_USERNAME"]
    password = os.environ["MQTT_PASSWORD"]
    ca_file = os.environ["MQTT_TLS_CA_FILE"]
    topic = os.environ.get("MQTT_TOPIC", "roadsense/v1/imu/raw")
    expected_messages = int(os.environ.get("EXPECTED_MESSAGES", "1"))
    expected_samples = int(os.environ.get("EXPECTED_SAMPLES", "1"))
    expected_first_timestamp = os.environ.get("EXPECTED_FIRST_TIMESTAMP", "")
    timeout = float(os.environ.get("SUBSCRIBER_TIMEOUT_SECONDS", "30"))

    connected = threading.Event()
    finished = threading.Event()
    failure: list[str] = []
    received: dict[int, bytes] = {}
    run_id: str | None = None
    sample_count = 0
    last_sample_index: int | None = None
    first_timestamp: str | None = None

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"roadsense-test-subscriber-{uuid.uuid4()}",
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(username, password)
    client.tls_set(ca_certs=ca_file, tls_version=ssl.PROTOCOL_TLS_CLIENT)

    def on_connect(client, userdata, flags, reason_code, properties) -> None:
        del userdata, flags, properties
        if reason_code != 0:
            failure.append(f"subscriber connection rejected: {reason_code}")
            finished.set()
            return
        client.subscribe(topic, qos=1)
        connected.set()
        print(json.dumps({"event": "subscriber_ready", "topic": topic}), flush=True)

    def on_message(client, userdata, message) -> None:
        nonlocal run_id, sample_count, last_sample_index, first_timestamp
        del client, userdata
        try:
            payload = json.loads(message.payload)
            validate_raw_payload(payload)
            sequence_id = payload["sequence_id"]
            if sequence_id in received:
                if received[sequence_id] != message.payload:
                    raise ValueError("duplicate sequence_id has conflicting payload")
                return
            if sequence_id != len(received):
                raise ValueError("sequence_id is not contiguous")
            payload_run_id = payload["run_id"]
            if run_id is None:
                run_id = payload_run_id
            elif run_id != payload_run_id:
                raise ValueError("run_id changed during replay")
            for sample in payload["samples"]:
                index = sample["sample_index"]
                if last_sample_index is not None and index != last_sample_index + 1:
                    raise ValueError("sample_index is not contiguous across batches")
                last_sample_index = index
                if first_timestamp is None:
                    first_timestamp = sample["source_timestamp"]
                sample_count += 1
            received[sequence_id] = message.payload
            if len(received) == expected_messages:
                finished.set()
        except Exception as error:
            failure.append(str(error))
            finished.set()

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(host, port, keepalive=30)
        client.loop_start()
        if not connected.wait(timeout):
            raise TimeoutError("subscriber did not connect")
        if not finished.wait(timeout):
            raise TimeoutError("subscriber timed out waiting for messages")
        if failure:
            raise ValueError(failure[0])
        if len(received) != expected_messages:
            raise ValueError(f"expected {expected_messages} messages, got {len(received)}")
        if sample_count != expected_samples:
            raise ValueError(f"expected {expected_samples} samples, got {sample_count}")
        if expected_first_timestamp and first_timestamp != expected_first_timestamp:
            raise ValueError(
                f"expected first timestamp {expected_first_timestamp}, got {first_timestamp}"
            )
        print(
            json.dumps(
                {
                    "event": "subscriber_complete",
                    "messages": len(received),
                    "samples": sample_count,
                    "run_id": run_id,
                    "first_timestamp": first_timestamp,
                    "last_sample_index": last_sample_index,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as error:
        print(json.dumps({"event": "subscriber_failed", "message": str(error)}), flush=True)
        return 1
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    sys.exit(main())
