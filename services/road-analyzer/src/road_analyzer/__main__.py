from __future__ import annotations

import signal
import sys
import threading

from .config import AnalyzerConfig
from .events import emit, emit_error
from .mqtt_service import MqttRoadAnalyzer
from .registry import SessionRegistry
from .storage import AnalyzerStore


def main() -> int:
    stop_event = threading.Event()
    service = None
    store = None

    def request_stop(signum, frame) -> None:
        del signum, frame
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        config = AnalyzerConfig.from_environment()
        registry = SessionRegistry.load(config.session_registry_file)
        store = AnalyzerStore.connect_with_retry(config)
        service = MqttRoadAnalyzer(config, registry, store, stop_event)
        service.start()
        service.run()
        emit("analyzer_stopped")
        return 0
    except Exception as error:
        emit_error("analyzer_failed", error)
        return 1
    finally:
        if service is not None:
            service.close()
        if store is not None:
            store.close()


if __name__ == "__main__":
    sys.exit(main())
