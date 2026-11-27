# RoadSense

RoadSense is a distributed vehicle-vibration monitoring application built around the MUHOS inertial measurement unit (IMU) recordings. It replays sensor samples, computes one-second vibration features, identifies threshold-based high-vibration events, and displays results in a dashboard.

The system supports **two independent deployment modes**:

1. **Fully local:** all seven components run with Docker Compose on one Linux machine.
2. **CSC Rahti:** Mosquitto, Signal Processor, Road Analyzer, PostgreSQL and FastAPI run as private OpenShift services; Sensor Replay and Streamlit run on the laptop, connected using two loopback-only `oc port-forward` sessions.

The inferred events indicate **high vibration**, not verified potholes, road defects or safety classifications.

## Components and data flow

```text
MUHOS IMU archive -> Sensor Replay -> MQTT (Mosquitto) -> Signal Processor
                            |                              |
                            +---- run-complete message ----+
                                                           |
                                               MQTT feature messages
                                                           |
                                                    Road Analyzer
                                                       |       |
                                                  PostgreSQL  MQTT events
                                                       |
                                                    FastAPI
                                                       |
                                                    Streamlit
```

| Component | Purpose | Technology |
|---|---|---|
| Sensor Replay | Reads the private MUHOS tar archive, publishes timestamped IMU batches and a completion message | Python / MQTT |
| Mosquitto | Authenticated TLS MQTT broker with persistence | Mosquitto |
| Signal Processor | Computes 1-second median-baseline vibration RMS and peak deviations | Python, SQLite recovery journal |
| Road Analyzer | Applies vibration threshold, writes features/events idempotently and maintains an MQTT event outbox | Python |
| PostgreSQL | Persists sessions, runs, feature windows and events | PostgreSQL |
| FastAPI | Exposes read-only status, runs, features and events | Python / FastAPI |
| Streamlit | Visualizes recorded sessions and processing results | Python / Streamlit |

## Repository layout

```text
architecture/
  system.mmd                  Architecture source diagram
config/environments/local/
  .env.example                Private dataset path template
infrastructure/
  compose/
    local.yaml                Full local stack
    rahti-client.yaml         Laptop-only clients for Rahti mode
    rahti-client.env.example  Laptop/port-forward settings
    mosquitto/                Local broker configuration
  rahti/
    core.yaml.tpl             PostgreSQL, broker, storage, Services and policies
    migrate.yaml.tpl          One-shot schema migration Job
    apps.yaml.tpl             Processor, analyzer and API
    images.env.example        Immutable image reference template
    mosquitto/                OpenShift-compatible broker image
services/
  sensor-replay/
  signal-processor/
  road-analyzer/
  api/
  dashboard/
tools/
  prepare_local.sh
  prepare_rahti_secrets.sh
  validate_secrets.py
  publish_images.sh
  render_rahti.py
  deploy_rahti.sh
  verify_rahti.sh
  preflight.sh
docs/
  local-deployment.md
  rahti-deployment.md
  architecture.md
  verification.md
```

Each `services/` directory contains the service source, a Dockerfile, and requirements. Unit tests are retained for important application behavior. The MUHOS archives, generated credentials, container registry tokens and generated Rahti manifests are deliberately **not** included.

## Getting started

- **[Fully local deployment](docs/local-deployment.md)** — prerequisites, dataset, TLS/password setup, Compose, migrations, replay, dashboard, checks and teardown.
- **[Distributed Rahti deployment](docs/rahti-deployment.md)** — image publishing, private registry access, Rahti Secrets and deployments, laptop tunnels, replay and checks.
- [Architecture and data contract](docs/architecture.md)
- [Validation and troubleshooting](docs/verification.md)
- Architecture source: [Mermaid diagram](architecture/system.mmd)

## Dataset

Download the MUHOS IMU archive from the [MUHOS dataset project](https://m3s-kuura.github.io/muhos-dataset/). The default recording is `Bumpy Gravel - imu.tar`, containing `imu/bosch_imu.csv`. The expected default archive SHA-256 is `91d37ad4de7106d5038ed7bffe1e373db65e0f4771865da8975a216e76ed34f3`. Verify that your archive matches before running the replay. Data remain outside version control.

## Course submission

This repository is the runnable source and documentation. Follow the University's current course instructions for the required GitLab `Final-Project/` submission, architecture image and recorded demonstration. A GitHub repository by itself may not be the required final submission.
