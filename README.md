# RoadSense — MUHOS Vehicle Vibration Monitoring

> **Status: PLANNING ONLY.** This repository currently contains documentation and directory guides. No application code, container images, deployments, or cloud resources have been created.

RoadSense is the proposed final project for the University of Oulu **Software Defined Systems** course. It replays recorded vehicle-sensor measurements from the [MUHOS dataset](https://m3s-kuura.github.io/muhos-dataset/) and turns them into vibration summaries and events using independently deployable microservices.

## Key idea

A remote **VPS** acts as the external data-source and presentation node. **CSC Rahti (OpenShift/Kubernetes)** hosts message transport, processing, storage, and the API.

```text
VPS (Docker Compose)                                  CSC Rahti (OpenShift)
+------------------------------+                    +-----------------------------------+
| MUHOS CSV/JSON files         |                    | MQTT Mosquitto broker             |
|   -> Python sensor-replay ---+-- MQTT/TLS ------->|      |                            |
| Streamlit dashboard <--------+-- HTTPS/API -------+------ FastAPI <--- PostgreSQL     |
+------------------------------+                    |      ^                 ^          |
                                                   | Signal processor -> Road analyzer|
                                                   |      (via MQTT topics)           |
                                                   +-----------------------------------+
```

**Note:** The chart above is a conceptual diagram. See [detailed architecture](docs/01-architecture.md) and the [Mermaid diagram](architecture/road-sense.mmd) for data flow and trust boundaries.

## Project boundaries

- **Required MVP:** one Bosch IMU recording, deterministic sensor replay, MQTT, window-based vibration features, simple alerts, persisted results, FastAPI, and Streamlit visualization.
- **Planned second data source:** CAN speed, **only after** its timestamps and units are verified from real downloaded files.
- **Out of scope:** real-time hardware, clinical/medical inference, automatic pothole identification, ROS2, raw video, LiDAR, machine learning, production fleet tracking.
- **No fabricated claims:** the “roughness” metric is an exploratory vibration indicator, **not** a validated road-surface quality measurement. Speed and sensor orientation can affect results.
- **No implementation now:** directory READMEs are placeholders for later Codex phases.

## Start here

1. [Project charter and boundaries](docs/00-project-charter.md)
2. [Architecture](docs/01-architecture.md)
3. [Data formats and message contracts](docs/02-data-contracts.md)
4. [VPS + Rahti deployment plan](docs/03-vps-rahti-deployment.md)
5. [Security and operations](docs/04-security-operations.md)
6. [Acceptance tests and video walkthrough](docs/05-validation-demo.md)
7. [Course submission and evidence](docs/06-course-submission.md)
8. [Open decisions, assumptions, risks](docs/07-decisions-and-risks.md)
9. [Repository layout and implementation ownership](docs/08-repository-structure.md)
10. [Codex handoff rules](AGENTS.md)

## Ordered phases

| Phase | Goal | Instructions |
|---|---|---|
| 00 | Verify requirements and inspect MUHOS data | [Phase 00](phases/00-scope-and-data.md) |
| 01 | Prepare and secure the VPS | [Phase 01](phases/01-vps-foundation.md) |
| 02 | Build and prove replay through local MQTT | [Phase 02](phases/02-replay-and-mqtt.md) |
| 03 | Compute vibration features from streaming IMU | [Phase 03](phases/03-signal-processing.md) |
| 04 | Generate events and persist features | [Phase 04](phases/04-analysis-and-database.md) |
| 05 | Serve and visualize stored measurements | [Phase 05](phases/05-api-and-dashboard.md) |
| 06 | Move backend to Rahti and connect VPS | [Phase 06](phases/06-rahti-integration.md) |
| 07 | Validate, harden, document and demonstrate | [Phase 07](phases/07-final-validation.md) |

**Execution rule:** Codex implements **one phase at a time** and does not start the next until the current phase has met all acceptance criteria. All phases are presently unimplemented.

## Intended services

| Service | Runs on | Stack |
|---|---|---|
| `sensor-replay` | VPS | Python, Pandas, Paho-MQTT, Docker |
| `dashboard` | VPS | Streamlit, Plotly, Docker |
| `mqtt-broker` | Rahti (local copy for development) | Eclipse Mosquitto |
| `signal-processor` | Rahti | Python, NumPy/SciPy, Docker |
| `road-analyzer` | Rahti | Python, rules, PostgreSQL client |
| `api` | Rahti | FastAPI, PostgreSQL client |
| `postgres` | Rahti | PostgreSQL, persistent volume |

Initial prototypes run **on the VPS using Docker Compose**, with the backend migrated to Rahti only in Phase 06.

## External references

- [MUHOS dataset and downloads](https://m3s-kuura.github.io/muhos-dataset/)
- [Course homework and final project repository](https://gitlab.com/sdx-oulu/2024/hw-and-project)
- [Final Project instructions](https://gitlab.com/sdx-oulu/2024/hw-and-project/-/blob/main/Final-Project/README.md)

**Course requirement check:** confirm with the teacher whether an internet VPS outside Rahti satisfies any stated “local Docker” requirement; a VPS is an external node, but it is not physically local.

**Dataset check:** obtain dataset files, verify the dataset's attribution/license terms from the source, and do not commit raw recordings or personal information to GitHub.

## Submission

This GitHub repository is the **working project repository**. The course may require specific files in a separate GitLab fork under `Final-Project/`. Consult [submission plan](docs/06-course-submission.md) for the required final copy/sync, diagram, open-source reference, and demonstration link.
