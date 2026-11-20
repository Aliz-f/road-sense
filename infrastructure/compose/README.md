# Docker Compose

**Status: Phase 05 complete local Sensor Replay + MQTT + Signal Processor +
Road Analyzer + PostgreSQL + FastAPI + Streamlit stack verified. No remote
deployment exists.**

`preflight.compose.yaml` verifies the laptop daemon, Compose lifecycle, health
checks, an internal network, a read-only root filesystem, and absence of
published ports. It contains no RoadSense application service.

Phases 02–05 add the broker, feeder, processor, analyzer, migrations, database,
API, and dashboard on the **local laptop**. Phase 06
creates a separate VPS Compose deployment for only sensor-replay and dashboard.

`local.compose.yaml` currently contains Sensor Replay, Signal Processor, Road
Analyzer, PostgreSQL 16.6, FastAPI, Streamlit/Plotly, a migration job, a
TLS/authenticated Mosquitto broker, an auth-file initializer, and profile-gated
test containers. Only FastAPI (`127.0.0.1:8000`) and Streamlit
(`127.0.0.1:8501`) publish host ports. MQTT and database traffic stay on the
internal `roadsense-local_roadsense` network; API/dashboard HTTP also uses the
limited `roadsense-local_browser` network.
The database uses `roadsense-local-postgres-data`; routine `down` preserves it.
Local passwords, certificate keys, and dataset paths are generated under
Git-ignored paths by `../../tools/prepare_phase02_local.sh`.

See `../../docs/local-development.md`, the numbered specifications under
`../../phases/`, and `../../docs/architecture.md`.
