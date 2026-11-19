# Docker Compose

**Status: Phase 02 local Sensor Replay + MQTT stack verified. No later-phase
service or remote deployment exists.**

`preflight.compose.yaml` verifies the laptop daemon, Compose lifecycle, health
checks, an internal network, a read-only root filesystem, and absence of
published ports. It contains no RoadSense application service.

Phase 02 adds a broker and feeder on the **local laptop**; Phases 03–05 create
the complete **laptop Compose development stack**; Phase 06 creates a separate
VPS Compose deployment for only sensor-replay and dashboard.

`local.compose.yaml` currently contains Sensor Replay, a TLS/authenticated
Mosquitto broker, an auth-file initializer, and profile-gated test
subscriber/unit-test containers. The broker has no host-published port; all
MQTT traffic stays on the internal `roadsense-local_roadsense` network. Local
passwords, certificate keys, and dataset paths are generated under Git-ignored
paths by `../../tools/prepare_phase02_local.sh`.

See `../../docs/local-development.md`, the numbered specifications under
`../../phases/`, and `../../docs/architecture.md`.
