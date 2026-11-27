# System architecture and data contract

## Deployment topology

**Local mode:** all application components live in a single Docker Compose environment. Two private networks separate broker/database traffic from the laptop's HTTP-facing API and dashboard. PostgreSQL, Mosquitto and the processor journal use persistent Docker volumes.

**Rahti mode:** Mosquitto, Signal Processor, Road Analyzer, PostgreSQL and FastAPI run as OpenShift Deployments. Rahti provides `ClusterIP` internal Services, restricted security contexts, NetworkPolicies and three persistent volume claims. The laptop runs the Sensor Replay and Streamlit containers; authenticated `oc port-forward` sessions bridge the laptop's ports 18883 and 18000 to Rahti, both bound to `127.0.0.1`.

## MQTT contract

| Topic | Producer | Consumer |
|---|---|---|
| `roadsense/v1/imu/raw` | Sensor Replay | Signal Processor |
| `roadsense/v1/imu/run-complete` | Sensor Replay | Signal Processor |
| `roadsense/v1/imu/features` | Signal Processor | Road Analyzer |
| `roadsense/v1/events` | Road Analyzer | Optional monitoring |

The replay preserves source UTC timestamps, assigns a new UUID `run_id` for each run, and supplies monotonic sequence and sample indexes. Raw payloads preserve archive hash and member provenance. MQTT publishes use QoS 1; downstream services treat duplicate delivery as normal.

The processor uses one-second half-open **source-time** windows, anchored at the session's initial sample timestamp. For each acceleration vector `(x,y,z)` in mg:

```text
m = sqrt(x*x + y*y + z*z)
baseline = median(m values in window)
d = m - baseline
vibration_rms_mg = sqrt(mean(d*d))
peak_deviation_mg = max(abs(d))
```

Features include window indexes, original source bounds, the computed baseline, quality flags, algorithm version and original source provenance. The final partial window is emitted after the validated `run-complete` message and all raw batches have arrived.

The analyzer writes features and matched events to PostgreSQL. Default event rule: **vibration RMS ≥ 100 mg**, with a fixed rule version and deterministic event IDs. Its transactional outbox supports retrying event publication; the processor uses a SQLite recovery journal. Both consumers handle duplicate deliveries idempotently.

## Database and API

PostgreSQL stores `sessions`, `runs`, `feature_windows`, `events`, `heuristic_rules`, `event_outbox` and `schema_migrations`. Application migrations run before analyzer/API startup.

Read-only FastAPI endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health/live` | Process liveness |
| `GET /health/ready` | Database readiness |
| `GET /api/v1/status` | Aggregate counts and pending outbox |
| `GET /api/v1/sessions` | Available recordings |
| `GET /api/v1/runs` | Recorded replay runs |
| `GET /api/v1/runs/{run_id}/features` | Window measurements |
| `GET /api/v1/runs/{run_id}/events` | High-vibration events |

Collection endpoints support `limit` and `offset` pagination. Streamlit calls the API to populate the run selector, summary tables and plots.

## Data-quality limitations

The dataset does not establish sensor orientation relative to the vehicle. Magnitude-based vibration deviations are therefore used instead of labeling one axis as the vertical direction. The default 100 mg rule is exploratory: it does **not** validate pothole detection, road condition, road safety or incident severity. The application does not silently interpolate missing or non-monotonic timestamps.

## Security choices

- MQTT requires a username/password and CA-validated TLS.
- Raw datasets and secrets never enter the Git repository.
- PostgreSQL has no public listener in either mode.
- Rahti API and MQTT are internal-only; access from the laptop is via `oc port-forward --address 127.0.0.1`.
- Secrets and Docker image references are kept separate from source manifests.
- Container images are pinned by immutable digest for Rahti deployment.
- Periodic PVC backups are the operator's responsibility; deployment scripts do not back up data.
