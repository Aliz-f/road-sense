from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"required environment variable is empty: {name}")
    return value


def integer(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    archive_path: Path
    source_member: str
    source_archive_sha256: str
    session_id: str
    sensor_id: str
    run_id: str
    batch_size: int
    max_payload_bytes: int
    max_samples: int
    replay_rate: float
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_tls_ca_file: Path
    mqtt_topic: str
    mqtt_connect_retries: int
    mqtt_connect_timeout_seconds: float

    @classmethod
    def from_environment(cls) -> "ReplayConfig":
        dataset_root = Path(required("ROADSENSE_DATASET_CONTAINER_PATH"))
        run_id = os.getenv("RUN_ID", "").strip() or str(uuid.uuid4())
        try:
            uuid.UUID(run_id)
        except ValueError as error:
            raise ValueError("RUN_ID must be a UUID when supplied") from error
        try:
            replay_rate = float(os.getenv("REPLAY_RATE", "1.0"))
            connect_timeout = float(os.getenv("MQTT_CONNECT_TIMEOUT_SECONDS", "10"))
        except ValueError as error:
            raise ValueError("REPLAY_RATE and MQTT_CONNECT_TIMEOUT_SECONDS must be numeric") from error
        if replay_rate < 0:
            raise ValueError("REPLAY_RATE must be non-negative; 0 means no pacing")
        if connect_timeout <= 0:
            raise ValueError("MQTT_CONNECT_TIMEOUT_SECONDS must be positive")
        return cls(
            archive_path=dataset_root / required("ROADSENSE_MVP_ARCHIVE"),
            source_member=required("ROADSENSE_MVP_MEMBER"),
            source_archive_sha256=required("SOURCE_ARCHIVE_SHA256"),
            session_id=required("SESSION_ID"),
            sensor_id=os.getenv("SENSOR_ID", "bosch-xdk-110"),
            run_id=run_id,
            batch_size=integer("BATCH_SIZE", 64, 1, 512),
            max_payload_bytes=integer("MAX_PAYLOAD_BYTES", 131072, 1024, 1048576),
            max_samples=integer("MAX_SAMPLES", 0, 0, 10_000_000),
            replay_rate=replay_rate,
            mqtt_host=required("MQTT_HOST"),
            mqtt_port=integer("MQTT_PORT", 8883, 1, 65535),
            mqtt_username=required("MQTT_USERNAME"),
            mqtt_password=required("MQTT_PASSWORD"),
            mqtt_tls_ca_file=Path(required("MQTT_TLS_CA_FILE")),
            mqtt_topic=os.getenv("MQTT_TOPIC", "roadsense/v1/imu/raw"),
            mqtt_connect_retries=integer("MQTT_CONNECT_RETRIES", 10, 1, 100),
            mqtt_connect_timeout_seconds=connect_timeout,
        )
