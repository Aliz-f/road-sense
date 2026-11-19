# Docker Compose

**Status: Phase 04 local Sensor Replay + MQTT + Signal Processor + Road
Analyzer + PostgreSQL stack verified. No API/UI or remote deployment exists.**

`preflight.compose.yaml` verifies the laptop daemon, Compose lifecycle, health
checks, an internal network, a read-only root filesystem, and absence of
published ports. It contains no RoadSense application service.

Phases 02–04 add the broker, feeder, processor, analyzer, migrations, and
database on the **local laptop**; Phase 05 completes the **laptop Compose
development stack**; Phase 06
creates a separate VPS Compose deployment for only sensor-replay and dashboard.

`local.compose.yaml` currently contains Sensor Replay, Signal Processor, Road
Analyzer, PostgreSQL 16.6, a migration job, a TLS/authenticated Mosquitto
broker, an auth-file initializer, and profile-gated subscribers/test
containers. Broker, database, and services have no host-published ports. MQTT
and database traffic stay on the internal `roadsense-local_roadsense` network.
The database uses `roadsense-local-postgres-data`; routine `down` preserves it.
Local passwords, certificate keys, and dataset paths are generated under
Git-ignored paths by `../../tools/prepare_phase02_local.sh`.

See `../../docs/local-development.md`, the numbered specifications under
`../../phases/`, and `../../docs/architecture.md`.
