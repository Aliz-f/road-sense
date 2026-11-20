# Local laptop development setup

Phases 01-05 run on the laptop. This guide does not access or configure the
personal VPS or CSC Rahti.

## Verified host baseline (2026-11-19)

- Manjaro Linux, kernel 6.18.55-1-MANJARO, x86_64.
- 16 logical CPUs, 30 GiB host RAM (14 GiB available during inspection), and
  146 GiB free on the repository filesystem.
- Docker CLI 27.5.1, Docker Desktop 4.98.0, Engine 29.9.2, and Docker Compose
  5.6.1. Docker Desktop is running in context `desktop-linux` with 16 CPUs and
  approximately 8 GB RAM assigned to its VM.
- Storage driver `overlayfs`; Docker data root `/var/lib/docker` inside the
  Docker Desktop VM.

The Codex filesystem sandbox cannot open the Docker Desktop Unix socket even
though it is owned by the local user. Running the same read-only diagnostics
with explicit local-socket permission succeeded. This was a sandbox boundary,
not a Docker daemon or Unix group failure. Do not work around it with
`sudo docker`, socket `chmod`, or group changes.

## Private dataset configuration

The five archives remain under `data/raw/archives`, which is ignored by Git.
Do not extract or copy them into a tracked directory. Create the local config:

```sh
cp config/environments/local/.env.example config/environments/local/.env
```

Set `ROADSENSE_DATASET_ROOT` in the ignored file to the absolute archives
directory. This laptop uses:

```text
/home/alireza/aliz_projects/road-sense/data/raw/archives
```

The Sensor Replay Compose service uses this bind mount:

```yaml
volumes:
  - type: bind
    source: ${ROADSENSE_DATASET_ROOT:?set an absolute private dataset path}
    target: /data/archives
    read_only: true
```

The selected MVP input remains archive `Bumpy Gravel - imu.tar`, member
`imu/bosch_imu.csv`. The archive is read directly; no extracted CSV is needed.

## Local Compose boundary

The application Compose file uses one project name (`roadsense-local`), the
internal `roadsense` backend network, and the `browser` network shared only by
API and dashboard. Containers communicate using these service names:

| Service | Health/readiness signal | Host publication |
|---|---|---|
| `mqtt-broker` | authenticated TLS MQTT connection | none; internal Compose network only |
| `sensor-replay` | process/readiness state | none |
| `signal-processor` | authenticated raw/completion subscriptions and structured ready event | none |
| `road-analyzer` | DB and MQTT readiness | none |
| `postgres` | authenticated `SELECT 1` | none |
| `api` | HTTP `/health/ready` | `127.0.0.1:8000` |
| `dashboard` | HTTP health endpoint | `127.0.0.1:8501` |

Never use a bare port mapping such as `8000:8000`, because it binds all host
interfaces. Keep database traffic internal. Local MQTT authentication and
credentials are introduced with the broker in Phase 02 and remain in ignored
files.

## Preflight and lifecycle

The Phase 01 preflight contains one hardened BusyBox container, no application
service, volume, or published port. Its image tag and digest are pinned.

```sh
docker context show
docker desktop status
docker compose -f infrastructure/compose/preflight.compose.yaml config --quiet
./tools/validate_phase01.sh
```

The validation script always tears down its dedicated container and internal
network. Manual cleanup is:

```sh
docker compose -f infrastructure/compose/preflight.compose.yaml down --remove-orphans
```

Optional cache rollback, only if the image is not used elsewhere:

```sh
docker image rm docker.io/library/busybox:1.36.1
```

Phase 02 created `infrastructure/compose/local.compose.yaml`; Phase 03 added
Signal Processor and the `roadsense/v1/imu/run-complete` control path. Phase 04
added Road Analyzer, migrations, and PostgreSQL on the named
`roadsense-local-postgres-data` volume, plus broker/session persistence on
`roadsense-local-mqtt-data`. Phase 05 added FastAPI and Streamlit/Plotly. The
local broker limits a subscriber to one unacknowledged QoS message; the
processor and analyzer manually acknowledge only after processing so bounded
queues apply backpressure without blocking Paho callbacks. Generate the ignored local
credentials/certificates, then use the explicit environment and Compose paths
consistently:

```sh
./tools/prepare_phase02_local.sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml up --build -d --wait \
  mqtt-broker postgres signal-processor road-analyzer api dashboard
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm sensor-replay
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml ps
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml logs --tail=100
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml down --remove-orphans
```

Open `http://127.0.0.1:8501` for the dashboard or
`http://127.0.0.1:8000/docs` for the local OpenAPI UI. The one-shot replay can
be rerun with a new `run_id`; the dashboard lists stored runs through FastAPI.

The one-shot `analyzer-migrate` service runs automatically before the analyzer.
Use `./tests/phase05_e2e.sh` for the complete real-data API/dashboard pipeline
and `./tests/phase04_e2e.sh` for database/broker/process outage,
outbox, rotation, duplicate, and repeated-volume checks. Do not add `--volumes`
to routine teardown; that would delete local database and queued MQTT data.

The database password lives in the ignored
`config/environments/local/runtime/postgres/password` file. Preparation creates
it only for a new environment and preserves it under `--force`. Rotate it
explicitly, while PostgreSQL is available, with:

```sh
./tools/rotate_phase04_postgres_password.sh --apply
```

No password value is printed. If rotation is interrupted, retain the ignored
`password.previous` fallback and rerun the command; analyzer reconnects and
FastAPI database requests accept either staged credential until promotion.

## Troubleshooting and risk checklist

- Confirm `docker context show` is `desktop-linux` and `docker desktop status`
  is `running` before changing permissions or configuration.
- A socket error only inside a sandbox does not prove the daemon is down. Check
  `docker version` in the normal user terminal.
- The local broker publishes no host port. If a future debugging port is
  authorized, inspect conflicts with `ss -ltn` and bind it only to `127.0.0.1`.
- Use `docker compose config` before `up`; inspect with `docker compose ps` and
  `docker compose logs --tail=100`.
- The laptop already runs unrelated Minikube/course containers. Use the unique
  Compose project name and never run broad cleanup commands such as
  `docker system prune`.
- Keep at least several GB of Docker Desktop memory available for the
  seven-service stack; reassess the current 8 GB allocation if OOM events occur.
- Dataset mounts are read-only; raw archives, `.env` files, tokens, passwords,
  and certificates stay untracked.
- No local port is intentionally public, and no VPS/Rahti endpoint is used in
  Phases 01-05.
