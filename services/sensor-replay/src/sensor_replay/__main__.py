from __future__ import annotations

import signal
import sys
import threading

from .config import ReplayConfig
from .events import emit, emit_error
from .mqtt_client import MqttPublisher
from .parser import iter_imu_samples
from .replay import replay


def main() -> int:
    stop_event = threading.Event()

    def request_stop(signum, frame) -> None:
        del frame
        emit("shutdown_requested", signal=signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    publisher = None
    try:
        config = ReplayConfig.from_environment()
        emit(
            "replay_starting",
            run_id=config.run_id,
            session_id=config.session_id,
            source_member=config.source_member,
            batch_size=config.batch_size,
            replay_rate=config.replay_rate,
            max_samples=config.max_samples,
        )
        samples = iter_imu_samples(
            config.archive_path,
            config.source_member,
            config.source_archive_sha256,
            config.max_samples,
        )
        publisher = MqttPublisher(
            host=config.mqtt_host,
            port=config.mqtt_port,
            username=config.mqtt_username,
            password=config.mqtt_password,
            ca_file=str(config.mqtt_tls_ca_file),
            run_id=config.run_id,
            connect_retries=config.mqtt_connect_retries,
            connect_timeout_seconds=config.mqtt_connect_timeout_seconds,
            stop_event=stop_event,
        )
        publisher.start()
        messages, samples_published = replay(
            samples=samples,
            publisher=publisher,
            topic=config.mqtt_topic,
            run_id=config.run_id,
            session_id=config.session_id,
            sensor_id=config.sensor_id,
            source_archive_sha256=config.source_archive_sha256,
            source_member=config.source_member,
            batch_size=config.batch_size,
            max_payload_bytes=config.max_payload_bytes,
            replay_rate=config.replay_rate,
            stop_event=stop_event,
        )
        emit(
            "replay_finished" if not stop_event.is_set() else "replay_stopped",
            run_id=config.run_id,
            messages=messages,
            samples=samples_published,
        )
        return 0
    except Exception as error:
        emit_error("replay_failed", error)
        return 1
    finally:
        if publisher is not None:
            publisher.close()


if __name__ == "__main__":
    sys.exit(main())
