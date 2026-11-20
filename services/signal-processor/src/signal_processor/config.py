from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"required environment variable is empty: {name}")
    return value


def positive_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be numeric") from error
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def bounded_integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class ProcessorConfig:
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_tls_ca_file: Path
    raw_topic: str
    run_complete_topic: str
    feature_topic: str
    client_id: str
    connect_timeout_seconds: float
    publish_timeout_seconds: float
    queue_capacity: int
    ready_file: Path

    @classmethod
    def from_environment(cls) -> "ProcessorConfig":
        client_id = os.getenv(
            "PROCESSOR_MQTT_CLIENT_ID", "roadsense-signal-processor-local"
        ).strip()
        if not client_id or len(client_id.encode("utf-8")) > 128:
            raise ValueError("PROCESSOR_MQTT_CLIENT_ID must be 1-128 UTF-8 bytes")
        return cls(
            mqtt_host=required("MQTT_HOST"),
            mqtt_port=bounded_integer("MQTT_PORT", 8883, 1, 65535),
            mqtt_username=required("MQTT_USERNAME"),
            mqtt_password=required("MQTT_PASSWORD"),
            mqtt_tls_ca_file=Path(required("MQTT_TLS_CA_FILE")),
            raw_topic=os.getenv("MQTT_RAW_TOPIC", "roadsense/v1/imu/raw"),
            run_complete_topic=os.getenv(
                "MQTT_RUN_COMPLETE_TOPIC", "roadsense/v1/imu/run-complete"
            ),
            feature_topic=os.getenv(
                "MQTT_FEATURE_TOPIC", "roadsense/v1/imu/features"
            ),
            client_id=client_id,
            connect_timeout_seconds=positive_float(
                "MQTT_CONNECT_TIMEOUT_SECONDS", 10.0
            ),
            publish_timeout_seconds=positive_float(
                "MQTT_PUBLISH_TIMEOUT_SECONDS", 10.0
            ),
            queue_capacity=bounded_integer(
                "PROCESSOR_QUEUE_CAPACITY", 1024, 1, 100_000
            ),
            ready_file=Path(
                os.getenv("PROCESSOR_READY_FILE", "/tmp/signal-processor-ready")
            ),
        )
