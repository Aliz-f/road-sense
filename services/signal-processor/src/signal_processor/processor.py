from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta

from .model import (
    InvalidRawSample,
    RawBatch,
    RawSample,
    RunCompletion,
    RunMetadata,
    Window,
)
from .schema import (
    ALGORITHM_VERSION,
    BASELINE_METHOD,
    QUALITY_FLAG_ORDER,
    format_source_timestamp,
    parse_raw_message,
    parse_run_complete_message,
    validate_feature_payload,
)


GAP_THRESHOLD = timedelta(milliseconds=18)


class RunProcessor:
    def __init__(self, metadata: RunMetadata) -> None:
        self.metadata = metadata
        self.session_start: datetime | None = None
        self.active_window: Window | None = None
        self.expected_sequence_id = 0
        self.seen_sequences: dict[int, str] = {}
        self.seen_samples: dict[int, str] = {}
        self.last_sample_index: int | None = None
        self.last_source_time: datetime | None = None
        self.pending_flags: set[str] = set()
        self.pending_completion: RunCompletion | None = None
        self.completion_digest: str | None = None
        self.completed = False

    def _mark_discontinuity(self, flag: str) -> None:
        if self.active_window is not None:
            self.active_window.quality_flags.add(flag)
        self.pending_flags.add(flag)

    def _window_index(self, source_time: datetime) -> int:
        if self.session_start is None:
            raise RuntimeError("session start is not initialized")
        delta = source_time - self.session_start
        return delta.days * 86_400 + delta.seconds

    def _feature(self, window: Window, *, incomplete: bool) -> dict[str, object]:
        if self.session_start is None or not window.magnitudes_mg:
            raise RuntimeError("cannot emit an empty or unanchored window")
        baseline = float(statistics.median(window.magnitudes_mg))
        deviations = [magnitude - baseline for magnitude in window.magnitudes_mg]
        rms = math.sqrt(sum(value * value for value in deviations) / len(deviations))
        peak = max(abs(value) for value in deviations)
        flags = set(window.quality_flags)
        if incomplete:
            flags.add("incomplete_window")
        source_start = self.session_start + timedelta(seconds=window.window_index)
        payload: dict[str, object] = {
            "schema_version": 1,
            "run_id": self.metadata.run_id,
            "session_id": self.metadata.session_id,
            "sensor_id": self.metadata.sensor_id,
            "source_archive_sha256": self.metadata.source_archive_sha256,
            "source_member": self.metadata.source_member,
            "window_index": window.window_index,
            "source_start": format_source_timestamp(source_start),
            "source_end": format_source_timestamp(source_start + timedelta(seconds=1)),
            "sample_count": len(window.magnitudes_mg),
            "vibration_rms_mg": rms,
            "peak_deviation_mg": peak,
            "baseline_magnitude_mg": baseline,
            "baseline_method": BASELINE_METHOD,
            "quality_flags": [flag for flag in QUALITY_FLAG_ORDER if flag in flags],
            "algorithm_version": ALGORITHM_VERSION,
        }
        validate_feature_payload(payload)
        return payload

    def _accept_sample(self, sample: RawSample) -> list[dict[str, object]]:
        previous_digest = self.seen_samples.get(sample.sample_index)
        if previous_digest is not None:
            if previous_digest == sample.digest:
                return []
            self._mark_discontinuity("source_time_non_monotonic")
            self._mark_discontinuity("invalid_sample")
            raise ValueError("sample_index was reused with conflicting content")

        if self.last_sample_index is not None:
            if sample.sample_index <= self.last_sample_index:
                self._mark_discontinuity("source_time_non_monotonic")
                raise ValueError("sample_index moved backwards")
            if sample.sample_index != self.last_sample_index + 1:
                self._mark_discontinuity("source_time_gap")
        elif sample.sample_index != 0:
            self._mark_discontinuity("source_time_gap")

        if self.last_source_time is not None:
            if sample.source_time <= self.last_source_time:
                self._mark_discontinuity("source_time_non_monotonic")
                self._mark_discontinuity("invalid_sample")
                return []
            if sample.source_time - self.last_source_time > GAP_THRESHOLD:
                self._mark_discontinuity("source_time_gap")

        if self.session_start is None:
            self.session_start = sample.source_time
        window_index = self._window_index(sample.source_time)
        features: list[dict[str, object]] = []
        if self.active_window is None:
            self.active_window = Window(window_index=window_index)
        elif window_index > self.active_window.window_index:
            features.append(self._feature(self.active_window, incomplete=False))
            self.active_window = Window(window_index=window_index)
        elif window_index < self.active_window.window_index:
            self._mark_discontinuity("source_time_non_monotonic")
            self._mark_discontinuity("invalid_sample")
            return []

        self.active_window.quality_flags.update(self.pending_flags)
        self.pending_flags.clear()
        self.active_window.magnitudes_mg.append(
            math.sqrt(
                sample.acc_x_mg * sample.acc_x_mg
                + sample.acc_y_mg * sample.acc_y_mg
                + sample.acc_z_mg * sample.acc_z_mg
            )
        )
        self.seen_samples[sample.sample_index] = sample.digest
        self.last_sample_index = sample.sample_index
        self.last_source_time = sample.source_time
        return features

    def _mark_invalid_sample(self, sample: InvalidRawSample) -> None:
        if (
            sample.source_time is not None
            and self.session_start is not None
            and self.active_window is not None
        ):
            invalid_window_index = self._window_index(sample.source_time)
            if invalid_window_index == self.active_window.window_index:
                self.active_window.quality_flags.add("invalid_sample")
            elif invalid_window_index < self.active_window.window_index:
                self.active_window.quality_flags.add("source_time_non_monotonic")
                self.active_window.quality_flags.add("invalid_sample")
            self.pending_flags.add("invalid_sample")
            return
        self._mark_discontinuity("invalid_sample")

    def process(self, batch: RawBatch) -> list[dict[str, object]]:
        if batch.metadata != self.metadata:
            raise ValueError("run metadata changed for an existing run_id")
        previous_digest = self.seen_sequences.get(batch.sequence_id)
        if previous_digest is not None:
            if previous_digest == batch.digest:
                return []
            raise ValueError("sequence_id was reused with conflicting content")
        if self.completed:
            raise ValueError("raw batch arrived after run completion")
        if batch.sequence_id < self.expected_sequence_id:
            raise ValueError("sequence_id arrived out of order")
        if batch.sequence_id != self.expected_sequence_id:
            self._mark_discontinuity("source_time_gap")
        self.expected_sequence_id = batch.sequence_id + 1
        self.seen_sequences[batch.sequence_id] = batch.digest

        features: list[dict[str, object]] = []
        for sample in batch.samples:
            if isinstance(sample, InvalidRawSample):
                self._mark_invalid_sample(sample)
                continue
            features.extend(self._accept_sample(sample))
        features.extend(self._try_complete())
        return features

    def request_completion(
        self, completion: RunCompletion
    ) -> list[dict[str, object]]:
        if completion.metadata != self.metadata:
            raise ValueError("run-complete metadata does not match the raw run")
        if self.completion_digest is not None:
            if self.completion_digest == completion.digest:
                return []
            raise ValueError("run completion was reused with conflicting content")
        self.pending_completion = completion
        self.completion_digest = completion.digest
        return self._try_complete()

    def _try_complete(self) -> list[dict[str, object]]:
        completion = self.pending_completion
        if completion is None or self.completed:
            return []
        received_message_count = len(self.seen_sequences)
        if received_message_count < completion.raw_message_count:
            return []
        if received_message_count > completion.raw_message_count:
            raise ValueError("received more raw batches than run completion declares")
        if self.expected_sequence_id != completion.raw_message_count:
            raise ValueError("run completion conflicts with raw sequence IDs")
        if self.active_window is None or self.last_sample_index is None:
            raise ValueError("cannot complete a run without accepted samples")
        if self.last_sample_index > completion.last_sample_index:
            raise ValueError("run completion last_sample_index moved backwards")
        if self.last_sample_index < completion.last_sample_index:
            self._mark_discontinuity("source_time_gap")
        features = self.finalize()
        self.completed = True
        return features

    def finalize(self) -> list[dict[str, object]]:
        if self.active_window is None:
            return []
        feature = self._feature(self.active_window, incomplete=True)
        self.active_window = None
        return [feature]


class SignalEngine:
    def __init__(self) -> None:
        self.runs: dict[str, RunProcessor] = {}

    def process_message(self, encoded: bytes) -> list[dict[str, object]]:
        batch = parse_raw_message(encoded)
        run = self.runs.get(batch.metadata.run_id)
        if run is None:
            run = RunProcessor(batch.metadata)
            self.runs[batch.metadata.run_id] = run
        return run.process(batch)

    def complete_run(self, encoded: bytes) -> list[dict[str, object]]:
        completion = parse_run_complete_message(encoded)
        run = self.runs.get(completion.metadata.run_id)
        if run is None:
            run = RunProcessor(completion.metadata)
            self.runs[completion.metadata.run_id] = run
        return run.request_completion(completion)

    def finalize_all(self) -> list[dict[str, object]]:
        features: list[dict[str, object]] = []
        for run_id in sorted(self.runs):
            features.extend(self.runs[run_id].finalize())
        return features
