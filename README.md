# RoadSense — MUHOS Distributed Vehicle Vibration Monitoring

> **PHASE 06 PREPARED, NOT DEPLOYED.** Phases 00–05 run as a complete,
> tested Docker Compose application on the local Linux laptop. Phase 06 deploys
> only the backend to CSC Rahti; live Rahti verification still requires approval.

RoadSense is a University of Oulu Software Defined Systems course project. It
replays [MUHOS](https://m3s-kuura.github.io/muhos-dataset/) Bosch IMU data to
explore vehicle vibration patterns. Results are exploratory metrics, **not
validated pothole detection or road-safety classifications**.

## Deployment architecture

| Local Linux laptop — Docker Compose | CSC Rahti — OpenShift/OKD |
|---|---|
| Complete seven-service application for development and tests | Mosquitto, Signal Processor, Road Analyzer, PostgreSQL/PVC and FastAPI |
| Cross-environment demo: Sensor Replay and Streamlit only | Private ClusterIP Services reached through authenticated `oc port-forward` |

The complete local path is Sensor Replay → authenticated TLS Mosquitto → Signal
Processor → Road Analyzer → PostgreSQL → FastAPI → Streamlit. For the distributed
demo, two laptop-loopback forwards carry authenticated MQTT/TLS and private API
traffic to Rahti. No VPS, public MQTT LoadBalancer, public API Route, external
DNS, or source-IP allowlist is required.

[Architecture diagram](architecture/road-sense.mmd) ·
[Architecture explanation](docs/architecture.md) ·
[Phase 06 deployment guide](docs/phase-06-deployment-guide.md) ·
[Plan-correction report](docs/phase-06-plan-correction-report.md)

## Course alignment

The official final-project instructions, checked on 2026-11-27, require a
dockerized, non-monolithic application whose microservices communicate locally
and with Rahti resources. They do not state a VPS requirement. They also require
submission material in the course fork's `Final-Project/` directory, an
architecture image, and an approximately ten-minute recorded demonstration.
Recheck the [official instructions](https://gitlab.com/sdx-oulu/2024/hw-and-project/-/blob/main/Final-Project/README.md)
before submission because course material can change.

## Documentation

- [Codex operating instructions](AGENTS.md)
- [System architecture and network boundaries](docs/architecture.md)
- [Data, MQTT, database and API contracts](docs/contracts.md)
- [Operations](docs/operations.md)
- [Acceptance and submission](docs/acceptance-and-submission.md)
- [Known risks and open checks](docs/decisions-risks.md)

## Phases

| Phase | Objective | Instructions |
|---|---|---|
| 00 | Verify MUHOS files and course rules | [Open](phases/00-scope-data.md) |
| 01 | Prepare laptop Docker/Compose development | [Open](phases/01-local-foundation.md) |
| 02 | Replay IMU CSV through authenticated MQTT | [Open](phases/02-replay-mqtt.md) |
| 03 | Compute source-time vibration features | [Open](phases/03-signal-processing.md) |
| 04 | Add rules and persistent PostgreSQL storage | [Open](phases/04-analyzer-storage.md) |
| 05 | Add FastAPI and Streamlit | [Open](phases/05-api-dashboard.md) |
| 06 | Deploy the private backend to Rahti and demo from laptop | [Open](phases/06-rahti-integration.md) |
| 07 | Verify, demonstrate, document and submit | [Open](phases/07-final-submission.md) |

Raw recordings, credentials, certificate keys and generated deployment files
must remain outside Git. Images are digest-pinned on Rahti; MQTT remains
authenticated and TLS-verified; PostgreSQL remains internal.

The former personal-VPS plan was abandoned before deployment. Historical Phase
reports may describe it as the plan at that time; `infrastructure/vps` and the
optional public-endpoint templates are retained only as inactive history.
