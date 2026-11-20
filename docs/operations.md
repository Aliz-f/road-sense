# Operations — laptop first; deploy to personal VPS and CSC Rahti later

## Step 1 — Development on laptop
- Check laptop Docker Engine/Compose versions and available CPU/RAM/disk.
- Work in a local Git clone. Mount MUHOS CSV files from a private `data/raw` directory excluded from Git.
- Start full stack via Docker Compose: feeder, broker, processor, analyzer, DB, API, Streamlit.
- Use Docker's private service network. Bind developer-facing ports to 127.0.0.1; passwords stored outside Git.
- Run parser, numeric signal, MQTT, idempotency, REST and UI smoke tests. Do not move to deployment before a full local pass.
- Debug with `docker compose ps`, `docker compose logs` and controlled replay sessions.

Phase 01 verified the laptop baseline and standalone Compose preflight. Exact
versions, the private dataset mount convention, loopback port plan, lifecycle
commands, and troubleshooting are recorded in `local-development.md`. The
application Compose stack remains deferred to Phases 02–05.

Phase 05 completes the local stack with FastAPI at `http://127.0.0.1:8000` and
Streamlit at `http://127.0.0.1:8501`. Only those two ports are published, both
on loopback. MQTT and PostgreSQL remain unpublished. The dashboard calls the
API over Docker HTTP and never connects directly to MQTT or PostgreSQL.

Phases 04–05 use named PostgreSQL and Mosquitto volumes. Routine teardown must not
include `--volumes`. Mosquitto persists durable subscriptions/queued QoS 1
messages; PostgreSQL uses an authenticated SQL health check and the analyzer
retries temporary connection failures.

The ignored PostgreSQL password file remains stable under
`tools/prepare_phase02_local.sh --force`. Rotate it only with:

```sh
./tools/rotate_phase04_postgres_password.sh --apply
```

Rotation stages a fallback before changing the role and verifies the new login
before promotion. If interrupted, retain `password.previous` and rerun the
command after PostgreSQL is available; analyzer reconnects try both files.

## Step 2 — Package and publish
- Build versioned/pinned images from the *same source* tested locally.
- Push to an approved container registry only after test gates pass.
- Keep environment-specific hostnames, credentials, TLS certificates and data mounts out of images.

## Step 3 — Personal VPS deployment
- Before changing the VPS, confirm OS/resources, SSH/firewall, backup/rollback and Docker/Compose. Require owner's explicit approval for system changes.
- Install/configure Docker Compose securely and copy/mount MUHOS recordings to private read-only storage.
- Run only `sensor-replay` and `dashboard` as persistent Compose services, with configured Rahti MQTT and HTTPS API URLs.
- Prefer dashboard access through VPN/SSH tunnel; otherwise HTTPS + authentication. No public DB or broker on VPS.

## Step 4 — Rahti deployment
- Verify namespace, quotas, image registry, storage class, TLS/Routes, and credentials.
- Run broker, processor, analyzer, PostgreSQL with PVC and API using OpenShift/Kubernetes.
- Authenticate MQTT clients; restrict topics; validate MQTT TLS passthrough/alternative supported endpoint.
- Keep PostgreSQL an internal Service; expose API only over guarded HTTPS; protect all Secrets.
- Test the remote pipeline VPS feeder → Rahti processing/database/API → VPS dashboard.

## Reliability and evidence
Reconnection/restart tests, run/window IDs and idempotency, structured sanitized logs, persistent volume backup/restore, rollout and rollback instructions. No unapproved remote changes; no production claim before actual deployed end-to-end test.

## Current configuration boundary

The local Docker Desktop daemon, Phase 01 preflight, Phase 02 Sensor Replay,
Phase 03 source-time Signal Processor, the Phase 04 analyzer/PostgreSQL
pipeline, and the Phase 05 API/dashboard were verified. Private
dataset paths, credentials, and development certificate keys remain ignored;
no daemon settings or unrelated workloads were changed. Phase 04 test
containers/networks are removed after validation; the named local PostgreSQL
and Mosquitto volumes are intentionally retained to prove persistence. VPS
settings and Rahti
resources were not accessed or configured; their specifications, domains, TLS
support, and quotas remain unverified. See `phase-05-report.md` for exact local
commands and actual results.
