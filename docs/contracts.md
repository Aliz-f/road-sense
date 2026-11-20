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

## High-vibration event payload v1

The Road Analyzer publishes an event only when the configured inclusive rule
`vibration_rms_mg >= threshold_vibration_rms_mg` matches. The Phase 04 default
is `100.0 mg`, identified by rule version
`roadsense-high-vibration-rms-v1-t100`. Changing the threshold or semantics
requires a new rule version.

Required fields are `schema_version=1`, deterministic UUID `event_id`,
`event_type=high_vibration`, the feature's run/session/sensor/archive/member,
window index and source bounds, `algorithm_version`,
`heuristic_type=vibration_rms_threshold`, `rule_version`, `severity=high`,
`threshold_vibration_rms_mg`, `observed_vibration_rms_mg`, and the source
feature's ordered `quality_flags`. The event idempotency key is
`(run_id, window_index, algorithm_version, rule_version)`. Event delivery is
at least once; consumers use `event_id` to collapse exact MQTT duplicates.
The database transaction creates the event and its publication-outbox row
together. The analyzer retries pending rows on startup and while running, so a
committed event does not depend on feature redelivery. A crash after the broker
accepts QoS 1 but before the outbox mark can publish the same deterministic
event again.
These are exploratory vehicle-vibration events, not validated potholes, road
defects, or safety classifications.

## Database (implemented in Phase 04)

- `sessions`: immutable registry provenance including archive hash/member,
  full source bounds, row count, sensor ID, road-category label, and unknown
  orientation note. `(source_archive_sha256, source_member)` is unique.
- `runs`: unique `run_id`, session/sensor, observed feature bounds, status, and
  algorithm version. Replay rate remains nullable because feature v1 does not
  carry it. Status is `observed`; the analyzer receives no completion topic and
  therefore does not infer completion.
- `feature_windows`: unique `(run_id, window_index, algorithm_version)`, source
  interval, sample count, metrics, baseline method/value, quality flags, and a
  canonical payload SHA-256.
- `events`: deterministic event UUID plus unique
  `(run_id, window_index, algorithm_version, rule_version)`, feature reference,
  heuristic/rule, severity, threshold/observed values, and payload SHA-256.
- `heuristic_rules`: immutable binding from `rule_version` to heuristic type,
  comparison algorithm, event type, severity, and exact finite positive
  threshold. Events reference the complete rule configuration.
- `event_outbox`: one JSON payload per event UUID, publication attempts, last
  error/attempt, and nullable `published_at`. It commits with the event and is
  drained with QoS 1 at-least-once semantics.
- `schema_migrations`: applied file name, immutable checksum, and timestamp.

Feature/event persistence is one database transaction. Exact QoS 1 feature
duplicates reuse existing rows. A duplicate key with different canonical
content or provenance is rejected rather than overwritten. The named local
PostgreSQL volume persists across container recreation and has no host port.
Composite foreign keys ensure that run/session/sensor, feature/run/algorithm,
event/feature/observation, and event/rule values cannot drift independently.

## API (implemented in Phase 05)

The read-only FastAPI service exposes:

| Method and path | Response |
|---|---|
| `GET /health/live` | Process liveness; does not query dependencies. |
| `GET /health/ready` | Readiness after a read-only PostgreSQL query. |
| `GET /api/v1/sessions` | Paginated immutable recording provenance and run count. |
| `GET /api/v1/runs?session_id=...` | Paginated observed runs with feature/event counts. |
| `GET /api/v1/runs/{run_id}/features` | Paginated source-ordered feature windows for a UUID run. |
| `GET /api/v1/runs/{run_id}/events` | Paginated threshold events joined to exact feature source bounds and flags. |
| `GET /api/v1/status` | Aggregate session/run/feature/event and pending-outbox counts. |

Collection responses contain `items`, `limit`, `offset`, `count`, and `total`.
`limit` is 1–500 and `offset` is non-negative. Invalid query values or run UUIDs
return 422; a valid unknown run returns 404. Response models reject unexpected
fields and validate UUIDs, timestamps, non-negative metrics, enumerations, and
counts. Queries are fixed, parameterized, and executed in read-only database
transactions; the API exposes no arbitrary SQL or mutation endpoint.

## Required design checks

- Reject header drift, invalid timestamps, unknown acceleration units, and missing/non-numeric acceleration values.
- Preserve run_id, sequence_id, sample_index, source timestamp, archive hash, and member path end to end.
- Replay rate must not change features; duplicate batches/windows must not create duplicate persisted rows.
- Flag gaps, irregular/non-monotonic source time, and partial windows.
- Never describe derived events as validated potholes or safety classifications.
