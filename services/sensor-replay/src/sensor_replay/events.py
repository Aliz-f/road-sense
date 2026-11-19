from __future__ import annotations

import json
from datetime import datetime, timezone


def emit(event: str, **fields: object) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "level": "info",
        "event": event,
        **fields,
    }
    print(json.dumps(record, separators=(",", ":"), sort_keys=True), flush=True)


def emit_error(event: str, error: BaseException) -> None:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "level": "error",
        "event": event,
        "error_type": type(error).__name__,
        "message": str(error),
    }
    print(json.dumps(record, separators=(",", ":"), sort_keys=True), flush=True)
