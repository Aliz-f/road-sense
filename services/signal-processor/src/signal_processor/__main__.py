from __future__ import annotations

import signal
import sys
import threading

from .config import ProcessorConfig
from .events import emit, emit_error
from .mqtt_service import MqttSignalProcessor


def main() -> int:
    stop_event = threading.Event()

    def request_stop(signum, frame) -> None:
        del frame
        emit("processor_shutdown_requested", signal=signum)
        stop_event.set()

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    service = None
    try:
        config = ProcessorConfig.from_environment()
        service = MqttSignalProcessor(config, stop_event)
        service.start()
        service.run()
        emit("processor_stopped")
        return 0
    except Exception as error:
        emit_error("processor_failed", error)
        return 1
    finally:
        if service is not None:
            service.close()


if __name__ == "__main__":
    sys.exit(main())
