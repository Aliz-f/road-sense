from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterable, Iterator

from .events import emit
from .model import ImuSample
from .schema import build_raw_payload, encode_payload


def batches(samples: Iterable[ImuSample], batch_size: int) -> Iterator[list[ImuSample]]:
    batch: list[ImuSample] = []
    for sample in samples:
        batch.append(sample)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def replay(
    *,
    samples: Iterable[ImuSample],
    publisher,
    topic: str,
    run_id: str,
    session_id: str,
    sensor_id: str,
    source_archive_sha256: str,
    source_member: str,
    batch_size: int,
    max_payload_bytes: int,
    replay_rate: float,
    stop_event: threading.Event,
    monotonic: Callable[[], float] = time.monotonic,
    wait: Callable[[float], bool] | None = None,
) -> tuple[int, int]:
    wait = wait or stop_event.wait
    first_source_time = None
    replay_started = monotonic()
    message_count = 0
    sample_count = 0

    for sequence_id, batch in enumerate(batches(samples, batch_size)):
        if stop_event.is_set():
            break
        batch_source_time = batch[0].source_time
        if first_source_time is None:
            first_source_time = batch_source_time
        if replay_rate > 0:
            source_elapsed = (batch_source_time - first_source_time).total_seconds()
            target_elapsed = source_elapsed / replay_rate
            remaining = target_elapsed - (monotonic() - replay_started)
            if remaining > 0 and wait(remaining):
                break

        payload = build_raw_payload(
            run_id=run_id,
            session_id=session_id,
            sensor_id=sensor_id,
            sequence_id=sequence_id,
            source_archive_sha256=source_archive_sha256,
            source_member=source_member,
            samples=batch,
        )
        encoded = encode_payload(payload, max_payload_bytes)
        publisher.publish(topic, encoded)
        message_count += 1
        sample_count += len(batch)
        emit(
            "batch_published",
            run_id=run_id,
            sequence_id=sequence_id,
            first_sample_index=batch[0].sample_index,
            last_sample_index=batch[-1].sample_index,
            sample_count=len(batch),
            payload_bytes=len(encoded),
        )

    return message_count, sample_count
