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

Future sensor-replay Compose configuration must use this bind mount:

```yaml
volumes:
  - type: bind
    source: ${ROADSENSE_DATASET_ROOT:?set an absolute private dataset path}
    target: /data/archives
    read_only: true
```

The selected MVP input remains archive `Bumpy Gravel - imu.tar`, member
`imu/bosch_imu.csv`. The archive is read directly; no extracted CSV is needed.

## Planned local Compose boundary

The application Compose file is intentionally deferred to Phase 02. Use one
project name (`roadsense-local`) and one private application network. Containers
communicate using these service names:

| Service | Planned health signal | Host publication |
|---|---|---|
| `mqtt-broker` | authenticated MQTT connection | `127.0.0.1:1883`, development diagnostics only |
| `sensor-replay` | process/readiness state | none |
| `signal-processor` | subscriber/process state | none |
| `road-analyzer` | DB and MQTT readiness | none |
| `postgres` | `pg_isready` | none by default; if needed, `127.0.0.1:5432` only |
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

Future local startup/teardown commands, once Phase 02 creates the application
Compose file, will follow this shape:

```sh
docker compose --env-file config/environments/local/.env up --build --wait
docker compose ps
docker compose logs --tail=100
docker compose down --remove-orphans
```

Do not add `--volumes` to routine teardown after PostgreSQL persistence exists;
that would remove local database data.

## Troubleshooting and risk checklist

- Confirm `docker context show` is `desktop-linux` and `docker desktop status`
  is `running` before changing permissions or configuration.
- A socket error only inside a sandbox does not prove the daemon is down. Check
  `docker version` in the normal user terminal.
- Inspect conflicts with `ss -ltn` and ensure all published RoadSense addresses
  remain `127.0.0.1`. At inspection time, 1883, 5432, 8000, and 8501 were free.
- Use `docker compose config` before `up`; inspect with `docker compose ps` and
  `docker compose logs --tail=100`.
- The laptop already runs unrelated Minikube/course containers. Use the unique
  Compose project name and never run broad cleanup commands such as
  `docker system prune`.
- Keep at least several GB of Docker Desktop memory available for the future
  seven-service stack; reassess the current 8 GB allocation if OOM events occur.
- Dataset mounts are read-only; raw archives, `.env` files, tokens, passwords,
  and certificates stay untracked.
- No local port is intentionally public, and no VPS/Rahti endpoint is used in
  Phases 01-05.
