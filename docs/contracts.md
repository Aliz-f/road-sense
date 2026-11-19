# Data and API contracts

Source profile: [MUHOS dataset profile](dataset-profile.md). The Bosch portions below are verified against all three supplied Bosch CSV files. CAN SPEED remains unverified and is excluded from the MVP.

## Verified source contract

The accepted Bosch v1 CSV header is exactly:

    timestamp,acc_x_mg,acc_y_mg,acc_z_mg,mag_x_uT,mag_y_uT,mag_z_uT,mag_r_uT,gyro_x_mdeg,gyro_y_mdeg,gyro_z_mdeg

- timestamp is recording time in UTC RFC 3339 form with a Z suffix.
- Acceleration values are signed integers in mg; magnetic values are labelled uT; gyroscope values are labelled mdeg.
- The source has no row ID. Replay assigns zero-based sample_index in source order. It must not modify source timestamps or interpolate samples.
- Sensor orientation relative to the vehicle is unknown. No axis may be called vertical. sensor_id for these files is bosch-xdk-110.
- A session registry maps session_id to road label, archive SHA-256, member path, first/last timestamp, and row count. A changed hash is a different source revision and must not silently reuse provenance.

## MQTT v1 topics

| Topic | Producer | Consumer | Status |
|---|---|---|---|
| roadsense/v1/imu/raw | sensor-replay | signal-processor | MVP |
| roadsense/v1/imu/run-complete | sensor-replay | signal-processor | MVP control message |
| roadsense/v1/imu/features | signal-processor | road-analyzer | MVP |
| roadsense/v1/events | road-analyzer | optional monitoring | MVP |
| roadsense/v1/can/speed | sensor-replay | analyzer | Reserved; disabled until SPEED unit is verified |

## Raw IMU payload v1

| Required field | Contract |
|---|---|
| schema_version | Integer 1 |
| run_id | UUID created once for a replay execution |
| session_id | Stable registry ID, e.g. bumpy-gravel-20261019 |
| sensor_id | bosch-xdk-110 for the inspected CSVs |
| sequence_id | Zero-based, monotonically increasing batch number within run_id |
| source_archive_sha256 | Lowercase 64-character hash from session provenance |
| source_member | Exact tar member path |
| acceleration_unit | Literal mg; other values are rejected |
| samples | Non-empty ordered array; Phase 02 must set and test a message-size cap |

Each sample requires source_timestamp, zero-based sample_index, acc_x_mg, acc_y_mg, and acc_z_mg. Timestamp and index must be strictly increasing within a valid source stream. Magnetometer and gyroscope fields may be carried only with their original unit-bearing names; they are not MVP feature inputs. Replay/publish time, if added, must be named published_at and never substituted for source_timestamp.

The raw-message idempotency key is (run_id, sequence_id). Re-delivery of the same key must contain identical source samples; conflicting reuse is an error.

## Replay completion payload v1

After every raw QoS 1 publish for a successful non-empty replay has been
acknowledged, Sensor Replay publishes one QoS 1 control message to
`roadsense/v1/imu/run-complete`. Required fields are `schema_version=1`,
`event=run_complete`, the same `run_id`, `session_id`, `sensor_id`,
`source_archive_sha256`, and `source_member` as the raw stream, plus positive
`raw_message_count` and `sample_count`, zero-based `last_sequence_id`, and
zero-based `last_sample_index`. The following relationships are required:

    last_sequence_id = raw_message_count - 1
    last_sample_index = sample_count - 1

The completion idempotency key is `(run_id, event)`. An identical QoS 1
redelivery is ignored; conflicting content or provenance is rejected. Because
MQTT does not promise ordering across different topics, the processor may
receive the control message before one or more raw messages. It stores the
message and finalizes only after the declared number of distinct, contiguous
raw sequence IDs has arrived. A completion message never stops the processor;
it closes only the named run.

## Feature payload v1 and processing agreement

Windows are one-second, half-open source-time intervals anchored at the first session timestamp. For time t, window_index is floor((t - session_start) / 1 second). Replay speed and wall-clock delays do not affect membership. Do not interpolate or let a window cross a source restart.

For each accepted acceleration vector:

1. Compute magnitude m = sqrt(x² + y² + z²) in mg.
2. Set the window baseline b to the median magnitude.
3. Compute deviations d = m - b.
4. Emit vibration_rms_mg = sqrt(mean(d²)) and peak_deviation_mg = max(abs(d)).

This v1 definition is orientation-robust but exploratory. It removes a per-window magnitude baseline; it is not a calibrated gravity solution or a pothole/safety metric.

Required feature fields are schema_version=1, run_id, session_id, sensor_id,
source_archive_sha256, source_member, window_index, source_start, source_end,
sample_count, vibration_rms_mg, peak_deviation_mg, baseline_magnitude_mg,
baseline_method=window_magnitude_median, quality_flags, and
algorithm_version=roadsense-vibration-v1. source_start is the inclusive
source-time window boundary and source_end is the exclusive boundary exactly
one second later. Source archive/member provenance is carried through from the
raw batch. The feature idempotency key is (run_id, window_index,
algorithm_version).

quality_flags is an ordered array. Defined v1 values are source_time_gap,
source_time_non_monotonic, incomplete_window, and invalid_sample. The inspected
cadence has a 12 ms median; an adjacent interval greater than 18 ms, a missing
sequence, or a missing sample index is a source_time_gap. Exact QoS 1 batch and
sample duplicates are ignored. Conflicting reuse of an idempotency key is
rejected. Non-monotonic or invalid samples are not silently coerced or
interpolated; they are skipped and the affected window is flagged.

A window is emitted as complete only after an accepted sample reaches a later
source-time window. The still-open window is emitted with `incomplete_window`
after its validated replay-completion message and all declared raw batches
have arrived. Explicit graceful processor shutdown remains a fallback for a
run whose producer cannot send completion. Wall-clock inactivity is not a run
boundary because it would make results depend on replay rate or broker delays.
Phase 03 tests cover partial final windows, early and duplicate completion,
gaps, duplicates, invalid samples, and replay-rate invariance.

The local broker limits each subscriber to one unacknowledged QoS message.
The processor acknowledges a raw or completion message only after validation,
processing, and any feature publication. Its Paho network callback performs a
non-blocking insertion into a bounded queue. An unexpected full queue is a
fatal, non-acknowledged error rather than a blocking callback or silent drop.

## CAN SPEED gate

Supplied records contain numeric epoch timestamps and decoded message=SPEED, signal=SPEED values, but no unit. The CAN topic remains disabled. Before enabling it, record an authoritative unit source, conversion, clock/timezone interpretation, and alignment tolerance here. A future payload must include explicit speed_unit; unknown or invalid units are rejected.

## Database (proposed)

- sessions: immutable provenance including archive hash/member, source bounds, row count, sensor ID, road-category label, and orientation note.
- runs: unique run_id, session, replay rate, start/end/status, and algorithm version.
- feature_windows: unique feature idempotency key, source interval, sample count, metrics, baseline method/value, and quality flags.
- events: run/window reference, heuristic type, rule version, and severity.

MQTT QoS 1 duplicates use idempotent inserts/upserts. A duplicate key with different content must fail rather than overwrite provenance.

## API (proposed)

GET /health/live, /health/ready, /api/v1/sessions, /api/v1/runs, /api/v1/runs/{id}/features, /api/v1/runs/{id}/events, and /api/v1/status. Responses are JSON with validation and pagination; no arbitrary SQL exposure.

## Required design checks

- Reject header drift, invalid timestamps, unknown acceleration units, and missing/non-numeric acceleration values.
- Preserve run_id, sequence_id, sample_index, source timestamp, archive hash, and member path end to end.
- Replay rate must not change features; duplicate batches/windows must not create duplicate persisted rows.
- Flag gaps, irregular/non-monotonic source time, and partial windows.
- Never describe derived events as validated potholes or safety classifications.
