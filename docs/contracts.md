# Data and API contracts (proposed)

Source: https://m3s-kuura.github.io/muhos-dataset/

**Do not treat this as a verified data dictionary.** Phase 00 must inspect real extracted Bosch CSV headers, sampling interval, timestamps, timezone, sensor axes, units, missing values and attribution. Some examples in documentation use X/Y/Z accelerometer values measured in mg; original CSV column names must be verified.

## MQTT v1 topics
| Topic | Producer | Consumer |
|---|---|---|
| roadsense/v1/imu/raw | sensor-replay | signal-processor |
| roadsense/v1/imu/features | signal-processor | road-analyzer |
| roadsense/v1/events | road-analyzer | optional monitoring |
| roadsense/v1/can/speed | sensor-replay | analyzer, post-MVP only |

## Raw payload required fields
schema_version=1, run_id (unique replay execution), session_id (source recording), sensor_id, sequence (batch order), samples (recorded_at + sample_index + 3 acceleration axes + units). Message sizes bounded, timestamps are recording time, not replay time.

## Feature payload required fields
schema_version=1, run_id, session_id, window_index, source_start/source_end, sample_count, vibration_rms_mg, peak_deviation_mg, quality_flags, algorithm_version. Values must be computed from real data or flagged as synthetic in tests.

## Processing agreement
Group by source-time windows (initially 1 s); subtract/document baseline to mitigate static gravity; calculate dynamic vibration RMS, peak absolute deviation and quality flags. Verify gravity treatment and axis orientation. Threshold events are heuristic indicators only. Different speeds confound cross-recording comparisons.

## Database (proposed)
sessions (recording provenance, road category); runs (unique run_id, replay rate, algorithm version); feature_windows (unique run_id/window_index, recorded time, features, quality); events (run_id, window, type, rule version, severity). Idempotent upserts for MQTT QoS1 duplicates.

## API (proposed)
GET /health/live, /health/ready, /api/v1/sessions, /api/v1/runs, /api/v1/runs/{id}/features, /api/v1/runs/{id}/events, /api/v1/status. JSON responses, pagination, validation, no arbitrary SQL exposure.

## Design checks
Unknown/invalid units rejected; replay rate should not change calculated features; duplicate batches must not create duplicate persisted windows; gaps/irregular time must be flagged.
