from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from pathlib import Path

from psycopg.conninfo import make_conninfo


RULE_VERSION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


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


def optional_path(name: str) -> Path | None:
    value = os.getenv(name, "").strip()
    return Path(value) if value else None


def mqtt_topic(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    if not value or "+" in value or "#" in value:
        raise ValueError(f"{name} must be a non-empty concrete MQTT topic")
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
    postgres_password: str | None
    postgres_password_file: Path | None
    postgres_previous_password_file: Path | None
    postgres_connect_timeout_seconds: int
    postgres_connect_retries: int
    postgres_connect_retry_delay_seconds: float
    session_registry_file: Path
    vibration_rms_threshold_mg: float
    rule_version: str
    ready_file: Path
    outbox_poll_seconds: float

    def postgres_password_candidates(self) -> tuple[str, ...]:
        candidates: list[str] = []
        if self.postgres_password_file is not None:
            candidates.append(self._read_password_file(self.postgres_password_file))
            previous = self.postgres_previous_password_file
            if previous is not None and previous.is_file():
                previous_password = self._read_password_file(previous)
                if previous_password not in candidates:
                    candidates.append(previous_password)
        elif self.postgres_password is not None:
            candidates.append(self.postgres_password)
        if not candidates:
            raise ValueError("no PostgreSQL password source is configured")
        return tuple(candidates)

    @staticmethod
    def _read_password_file(path: Path) -> str:
        try:
            value = path.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as error:
            raise ValueError(f"cannot read PostgreSQL password file: {path}") from error
        if not value or "\n" in value or "\r" in value:
            raise ValueError(f"PostgreSQL password file must contain one non-empty line: {path}")
        return value

    def postgres_dsn(self, password: str) -> str:
        return make_conninfo(
            host=self.postgres_host,
            port=self.postgres_port,
            dbname=self.postgres_db,
            user=self.postgres_user,
            password=password,
            connect_timeout=self.postgres_connect_timeout_seconds,
        )

    @classmethod
    def from_environment(cls) -> "AnalyzerConfig":
        threshold = positive_float("ANALYZER_VIBRATION_RMS_THRESHOLD_MG", 100.0)
        rule_version = os.getenv(
            "ANALYZER_RULE_VERSION", "roadsense-high-vibration-rms-v1-t100"
        ).strip()
        if not rule_version:
            raise ValueError("ANALYZER_RULE_VERSION must be non-empty")
        if not RULE_VERSION_PATTERN.fullmatch(rule_version):
            raise ValueError(
                "ANALYZER_RULE_VERSION must use lowercase letters, digits, dot, underscore, or hyphen"
            )
        password = os.getenv("POSTGRES_PASSWORD", "").strip() or None
        password_file = optional_path("POSTGRES_PASSWORD_FILE")
        if password is not None and password_file is not None:
            raise ValueError("configure only one of POSTGRES_PASSWORD or POSTGRES_PASSWORD_FILE")
        if password is None and password_file is None:
            raise ValueError("POSTGRES_PASSWORD_FILE is required")
        previous_password_file = optional_path("POSTGRES_PREVIOUS_PASSWORD_FILE")
        if password_file is None and previous_password_file is not None:
            raise ValueError("POSTGRES_PREVIOUS_PASSWORD_FILE requires POSTGRES_PASSWORD_FILE")
        feature_topic = mqtt_topic("MQTT_FEATURE_TOPIC", "roadsense/v1/imu/features")
        event_topic = mqtt_topic("MQTT_EVENT_TOPIC", "roadsense/v1/events")
        if feature_topic == event_topic:
            raise ValueError("MQTT feature and event topics must differ")
        client_id = os.getenv(
            "ANALYZER_MQTT_CLIENT_ID", "roadsense-road-analyzer-local"
        ).strip()
        if not client_id or len(client_id.encode("utf-8")) > 128:
            raise ValueError("ANALYZER_MQTT_CLIENT_ID must be 1-128 UTF-8 bytes")
        return cls(
            mqtt_host=required("MQTT_HOST"),
            mqtt_port=bounded_integer("MQTT_PORT", 8883, 1, 65535),
            mqtt_username=required("MQTT_USERNAME"),
            mqtt_password=required("MQTT_PASSWORD"),
            mqtt_tls_ca_file=Path(required("MQTT_TLS_CA_FILE")),
            feature_topic=feature_topic,
            event_topic=event_topic,
            client_id=client_id,
            connect_timeout_seconds=positive_float("MQTT_CONNECT_TIMEOUT_SECONDS", 10.0),
            publish_timeout_seconds=positive_float("MQTT_PUBLISH_TIMEOUT_SECONDS", 10.0),
            queue_capacity=bounded_integer("ANALYZER_QUEUE_CAPACITY", 1024, 1, 100_000),
            postgres_host=required("POSTGRES_HOST"),
            postgres_port=bounded_integer("POSTGRES_PORT", 5432, 1, 65535),
            postgres_db=required("POSTGRES_DB"),
            postgres_user=required("POSTGRES_USER"),
            postgres_password=password,
            postgres_password_file=password_file,
            postgres_previous_password_file=previous_password_file,
            postgres_connect_timeout_seconds=bounded_integer(
                "POSTGRES_CONNECT_TIMEOUT_SECONDS", 5, 1, 60
            ),
            postgres_connect_retries=bounded_integer(
                "POSTGRES_CONNECT_RETRIES", 30, 1, 300
            ),
            postgres_connect_retry_delay_seconds=positive_float(
                "POSTGRES_CONNECT_RETRY_DELAY_SECONDS", 1.0
            ),
            session_registry_file=Path(
                os.getenv("ANALYZER_SESSION_REGISTRY_FILE", "/app/session-registry.json")
            ),
            vibration_rms_threshold_mg=threshold,
            rule_version=rule_version,
            ready_file=Path(os.getenv("ANALYZER_READY_FILE", "/tmp/road-analyzer-ready")),
            outbox_poll_seconds=positive_float("ANALYZER_OUTBOX_POLL_SECONDS", 1.0),
        )
