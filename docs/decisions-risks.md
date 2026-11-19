# Decisions and risks

## Fixed decisions
- Dataset: MUHOS; initial sensor: Bosch IMU.
- Host layout: VPS replaces personal computer as producer + dashboard. Rahti handles backend.
- Current work: docs and skeleton ONLY; Codex to implement later phase by phase.
- No ML, ROS2, LiDAR, cameras or live device integration in MVP.

## Proposed (reviewable)
MQTT/Mosquitto; Python feeder, signal processor, analyzer; PostgreSQL, FastAPI, Streamlit; Docker/Compose + Kubernetes/OpenShift. Initial one-second windows and simple configurable threshold.

## Open decisions / checks
1. Teacher must clarify whether VPS counts for requested 'local Docker' requirement; keep laptop Compose fallback.
2. Verify exact MUHOS file formats, download availability, schema, sampling rate, mounting, timestamps and license.
3. Validate CAN speed units/timestamp compatibility before optional extension.
4. Inspect VPS OS/resources/domain and access policies before installation.
5. Check Rahti MQTT/TLS route capabilities, quotas, storage and credentials.
6. Decide dashboard/API access control before public exposure.

## Major risks and responses
- Non-compliant coursework topology: teacher signoff, local demo fallback.
- Misleading road-quality labels: call outputs vibration metrics only and document speed confound.
- Bad unit/time handling: Phase 00 profiling, fixtures and numeric tests.
- Duplicate or lost MQTT delivery: QoS1 + run/window uniqueness and retries.
- Public endpoint compromise: TLS/auth/topic ACL, secrets, no direct DB.
- Quota/disk/data size: start with one small recording, limit payloads and persist processed features.
- Data loss: PVC backup and restore test; no unreviewed destructive migrations.
