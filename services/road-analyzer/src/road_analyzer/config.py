from __future__ import annotations

import math
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
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
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
class AnalyzerConfig:
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    mqtt_tls_ca_file: Path
    feature_topic: str
    event_topic: str
    client_id: str
    connect_timeout_seconds: float
    publish_timeout_seconds: float
    queue_capacity: int
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_connect_timeout_seconds: int
    postgres_connect_retries: int
    session_registry_file: Path
    vibration_rms_threshold_mg: float
    rule_version: str
    ready_file: Path

    @property
    def postgres_dsn(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password} "
            f"connect_timeout={self.postgres_connect_timeout_seconds}"
        )

    @classmethod
    def from_environment(cls) -> "AnalyzerConfig":
        threshold = positive_float("ANALYZER_VIBRATION_RMS_THRESHOLD_MG", 100.0)
        rule_version = os.getenv(
            "ANALYZER_RULE_VERSION", "roadsense-high-vibration-rms-v1-t100"
        ).strip()
        if not rule_version:
            raise ValueError("ANALYZER_RULE_VERSION must be non-empty")
        return cls(
            mqtt_host=required("MQTT_HOST"),
            mqtt_port=bounded_integer("MQTT_PORT", 8883, 1, 65535),
            mqtt_username=required("MQTT_USERNAME"),
            mqtt_password=required("MQTT_PASSWORD"),
            mqtt_tls_ca_file=Path(required("MQTT_TLS_CA_FILE")),
            feature_topic=os.getenv("MQTT_FEATURE_TOPIC", "roadsense/v1/imu/features"),
            event_topic=os.getenv("MQTT_EVENT_TOPIC", "roadsense/v1/events"),
            client_id=os.getenv("ANALYZER_MQTT_CLIENT_ID", "roadsense-road-analyzer-local"),
            connect_timeout_seconds=positive_float("MQTT_CONNECT_TIMEOUT_SECONDS", 10.0),
            publish_timeout_seconds=positive_float("MQTT_PUBLISH_TIMEOUT_SECONDS", 10.0),
            queue_capacity=bounded_integer("ANALYZER_QUEUE_CAPACITY", 1024, 1, 100_000),
            postgres_host=required("POSTGRES_HOST"),
            postgres_port=bounded_integer("POSTGRES_PORT", 5432, 1, 65535),
            postgres_db=required("POSTGRES_DB"),
            postgres_user=required("POSTGRES_USER"),
            postgres_password=required("POSTGRES_PASSWORD"),
            postgres_connect_timeout_seconds=bounded_integer(
                "POSTGRES_CONNECT_TIMEOUT_SECONDS", 5, 1, 60
            ),
            postgres_connect_retries=bounded_integer(
                "POSTGRES_CONNECT_RETRIES", 30, 1, 300
            ),
            session_registry_file=Path(
                os.getenv("ANALYZER_SESSION_REGISTRY_FILE", "/app/session-registry.json")
            ),
            vibration_rms_threshold_mg=threshold,
            rule_version=rule_version,
            ready_file=Path(os.getenv("ANALYZER_READY_FILE", "/tmp/road-analyzer-ready")),
        )
