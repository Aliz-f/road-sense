from __future__ import annotations

import json
import os
import ssl
import sys
import threading
import uuid

import paho.mqtt.client as mqtt

from .schema import validate_event_payload


def main() -> int:
    expected_run_id = os.environ.get("EXPECTED_RUN_ID", "")
    expected_events = int(os.environ.get("EXPECTED_EVENTS", "1"))
    timeout = float(os.environ.get("SUBSCRIBER_TIMEOUT_SECONDS", "30"))
    topic = os.environ.get("MQTT_EVENT_TOPIC", "roadsense/v1/events")
    subscribed = threading.Event()
    finished = threading.Event()
    failure: list[str] = []
    received: dict[str, dict[str, object]] = {}
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"roadsense-event-test-{uuid.uuid4()}",
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(os.environ["MQTT_USERNAME"], os.environ["MQTT_PASSWORD"])
    client.tls_set(ca_certs=os.environ["MQTT_TLS_CA_FILE"], tls_version=ssl.PROTOCOL_TLS_CLIENT)

    def on_connect(client, userdata, flags, reason_code, properties) -> None:
        del userdata, flags, properties
        if reason_code != 0:
            failure.append(f"event subscriber rejected: {reason_code}")
            finished.set()
            return
        client.subscribe(topic, qos=1)

    def on_subscribe(client, userdata, mid, reason_codes, properties) -> None:
        del client, userdata, mid, reason_codes, properties
        subscribed.set()
        print(json.dumps({"event": "event_subscriber_ready", "topic": topic}), flush=True)

    def on_message(client, userdata, message) -> None:
        del client, userdata
        try:
            payload = json.loads(message.payload)
            validate_event_payload(payload)
            if expected_run_id and payload["run_id"] != expected_run_id:
                return
            event_id = str(payload["event_id"])
            if event_id in received and received[event_id] != payload:
                raise ValueError("event_id was reused with conflicting content")
            received[event_id] = payload
            if len(received) == expected_events:
                finished.set()
        except Exception as error:
            failure.append(str(error))
            finished.set()

    client.on_connect = on_connect
    client.on_subscribe = on_subscribe
    client.on_message = on_message
    try:
        client.connect(os.environ["MQTT_HOST"], int(os.environ.get("MQTT_PORT", "8883")), keepalive=30)
        client.loop_start()
        if not subscribed.wait(timeout):
            raise TimeoutError("event subscriber did not subscribe")
        if not finished.wait(timeout):
            raise TimeoutError("event subscriber timed out")
        if failure:
            raise ValueError(failure[0])
        ordered = sorted(received.values(), key=lambda item: int(item["window_index"]))
        print(
            json.dumps(
                {
                    "event": "event_subscriber_complete",
                    "event_count": len(ordered),
                    "window_indices": [item["window_index"] for item in ordered],
                },
                separators=(",", ":"), sort_keys=True,
            ),
            flush=True,
        )
        return 0
    except Exception as error:
        print(json.dumps({"event": "event_subscriber_failed", "message": str(error)}), flush=True)
        return 1
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    sys.exit(main())
