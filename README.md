# RoadSense — MUHOS Distributed Vehicle Vibration Monitoring

> **PLANNING ONLY** — documentation, phase specifications, and folder guides are present. **No application code, server changes, deployments, or cloud resources have been created.**

RoadSense is a Software Defined Systems final-project design. It replays [MUHOS](https://m3s-kuura.github.io/muhos-dataset/) Bosch IMU measurements to explore vehicle vibration patterns in a distributed system. Vibration alerts are exploratory metrics, **not validated pothole or road-safety detection**.

## Hosting plan

| VPS — Docker Compose | CSC Rahti — OpenShift/Kubernetes |
|---|---|
| Private MUHOS dataset files | Mosquitto MQTT broker |
| Python Sensor Replay (CSV to MQTT) | Python Signal Processor |
| Streamlit/Plotly Dashboard | Road Analyzer |
| Connects outbound using MQTT/TLS and HTTPS | PostgreSQL and FastAPI |

Data flow: **MUHOS CSV → VPS Sensor Replay → MQTT/TLS → Rahti Broker → Signal Processor → MQTT features → Road Analyzer → PostgreSQL → FastAPI → HTTPS → VPS Dashboard**.

[View editable architecture diagram](architecture/road-sense.mmd) · [Architecture explanation](docs/architecture.md)

## Documentation

- [Codex operating instructions](AGENTS.md)
- [System architecture and network boundaries](docs/architecture.md)
- [Data contracts, MQTT topics, database, and API](docs/contracts.md)
- [VPS/Rahti deployment and security operations](docs/operations.md)
- [Acceptance tests, final demo and course submission](docs/acceptance-and-submission.md)
- [Known risks and open questions](docs/decisions-risks.md)
- [Repository layout and ownership](docs/repository-map.md)

## Eight phases — implement strictly in order

| Phase | Objective | Phase instructions |
|---|---|---|
| 00 | Verify MUHOS files and course rules | [Open](phases/00-scope-data.md) |
| 01 | Prepare and secure the VPS | [Open](phases/01-vps-foundation.md) |
| 02 | Replay IMU CSV using Python/Docker/MQTT | [Open](phases/02-replay-mqtt.md) |
| 03 | Compute vibration features from MQTT streams | [Open](phases/03-signal-processing.md) |
| 04 | Add rules and persistent PostgreSQL storage | [Open](phases/04-analyzer-storage.md) |
| 05 | Build FastAPI and the Streamlit dashboard | [Open](phases/05-api-dashboard.md) |
| 06 | Move backend services to Rahti; link VPS | [Open](phases/06-rahti-integration.md) |
| 07 | Verify, demonstrate, document and submit | [Open](phases/07-final-submission.md) |

Each phase document contains a **goal, prerequisites, tasks for Codex, deliverables, acceptance criteria, and a copyable Codex request**. Codex should implement one phase per branch and stop before starting the next.

## Planned structure

- `services/sensor-replay` — VPS Python/Pandas MQTT feeder
- `services/signal-processor` — Rahti Python/NumPy/SciPy feature calculation
- `services/road-analyzer` — Rahti Python rules and PostgreSQL writing
- `services/api` — Rahti FastAPI REST
- `services/dashboard` — VPS Streamlit/Plotly
- `infrastructure/vps` — VPS guides
- `infrastructure/compose` — local/VPS Docker Compose
- `infrastructure/rahti` — Kubernetes/OpenShift manifests
- `data` — acquisition docs, **not recordings**
- `tests` — future validation

## Scope and key decisions

MVP: replay one verified Bosch IMU CSV recording; compute time-window vibration RMS/peak; report high-vibration events; store and visualize results; demonstrate VPS-to-Rahti communication. Optional later: CAN speed after checking dataset units and timing. **No ML, ROS2, LiDAR, raw camera analysis, or real vehicle integration.**

**Course compliance question:** verify that a VPS counts for any assignment wording requiring a 'local Docker' component. If not, also demonstrate a laptop Compose client. The [official course repo](https://gitlab.com/sdx-oulu/2024/hw-and-project) may require submission in its GitLab `Final-Project/` path rather than this GitHub repository. Check [submission instructions](https://gitlab.com/sdx-oulu/2024/hw-and-project/-/blob/main/Final-Project/README.md) at Phase 00.

Data source: [MUHOS documentation](https://m3s-kuura.github.io/muhos-dataset/). License, citation, schema, timestamps and units must be verified from actual downloaded files before implementation. Never commit raw archives or credentials.

**Next action:** give Codex the [Phase 00 specification](phases/00-scope-data.md), but only when ready to begin implementation.
