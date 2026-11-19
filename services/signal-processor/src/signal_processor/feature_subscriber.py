from __future__ import annotations

import json
import os
import ssl
import sys
import threading
import uuid

import paho.mqtt.client as mqtt

from .schema import validate_feature_payload


def main() -> int:
    host = os.environ["MQTT_HOST"]
    port = int(os.environ.get("MQTT_PORT", "8883"))
    username = os.environ["MQTT_USERNAME"]
    password = os.environ["MQTT_PASSWORD"]
    ca_file = os.environ["MQTT_TLS_CA_FILE"]
    topic = os.environ.get("MQTT_FEATURE_TOPIC", "roadsense/v1/imu/features")
    expected_run_id = os.environ.get("EXPECTED_RUN_ID", "")
    expected_features = int(os.environ.get("EXPECTED_FEATURES", "1"))
    expected_first_window = int(os.environ.get("EXPECTED_FIRST_WINDOW_INDEX", "0"))
    timeout = float(os.environ.get("SUBSCRIBER_TIMEOUT_SECONDS", "30"))
    include_features = os.environ.get("SUBSCRIBER_INCLUDE_FEATURES", "true").lower() == "true"

    subscribed = threading.Event()
    finished = threading.Event()
    failure: list[str] = []
    received: dict[int, dict[str, object]] = {}

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"roadsense-feature-test-{uuid.uuid4()}",
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(username, password)
    client.tls_set(ca_certs=ca_file, tls_version=ssl.PROTOCOL_TLS_CLIENT)

    def on_connect(client, userdata, flags, reason_code, properties) -> None:
        del userdata, flags, properties
        if reason_code != 0:
            failure.append(f"feature subscriber rejected: {reason_code}")
            finished.set()
            return
        client.subscribe(topic, qos=1)

    def on_subscribe(client, userdata, mid, reason_codes, properties) -> None:
        del client, userdata, mid, reason_codes, properties
        subscribed.set()
        print(json.dumps({"event": "feature_subscriber_ready", "topic": topic}), flush=True)

    def on_message(client, userdata, message) -> None:
        del client, userdata
        try:
            payload = json.loads(message.payload)
            validate_feature_payload(payload)
            if expected_run_id and payload["run_id"] != expected_run_id:
                return
            window_index = payload["window_index"]
            if window_index in received:
                if received[window_index] != payload:
                    raise ValueError("duplicate feature key has conflicting payload")
                return
            if window_index != expected_first_window + len(received):
                raise ValueError("feature window_index is not contiguous")
            received[window_index] = payload
            if len(received) == expected_features:
                finished.set()
        except Exception as error:
            failure.append(str(error))
            finished.set()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    try:
        client.connect(host, port, keepalive=30)
        client.loop_start()
        if not subscribed.wait(timeout):
            raise TimeoutError("feature subscriber did not subscribe")
        if not finished.wait(timeout):
            raise TimeoutError("feature subscriber timed out")
        if failure:
            raise ValueError(failure[0])
        if len(received) != expected_features:
            raise ValueError(
                f"expected {expected_features} features, got {len(received)}"
            )
        ordered = [received[index] for index in sorted(received)]
        completion: dict[str, object] = {
            "event": "feature_subscriber_complete",
            "feature_count": len(ordered),
            "first_window_index": ordered[0]["window_index"],
            "last_window_index": ordered[-1]["window_index"],
        }
        if include_features:
            completion["features"] = ordered
        print(
            json.dumps(
                completion,
                separators=(",", ":"),
                sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as error:
        print(
            json.dumps({"event": "feature_subscriber_failed", "message": str(error)}),
            flush=True,
        )
        return 1
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    sys.exit(main())
