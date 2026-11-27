# Fully local deployment (Docker Compose)

This mode runs all seven components on a single Linux host. It does **not** need Rahti, `oc`, a VPS, a public domain, or a container registry account.

## 1. Prerequisites

Install Docker Engine or Docker Desktop with the Compose v2 plugin, Python 3, OpenSSL and Git. Verify:

```bash
docker version
docker compose version
python3 --version
openssl version
docker context show
```

Ensure Docker is running and enough free memory/disk is available for PostgreSQL, Streamlit and the Python services. Commands below run from the repository root. If you have other projects using host ports 8000 or 8501, stop them or adjust the port variables in your runtime environment.

## 2. Obtain the input dataset

Get the original MUHOS Bosch IMU archive from https://m3s-kuura.github.io/muhos-dataset/. Do not commit the archive to Git. For example, put the `Bumpy Gravel - imu.tar` file in a private folder:

```bash
mkdir -p "$HOME/datasets/roadsense"
# Copy your downloaded 'Bumpy Gravel - imu.tar' into this directory.
sha256sum "$HOME/datasets/roadsense/Bumpy Gravel - imu.tar"
```

For the dataset revision configured in the project, the expected SHA-256 is:

```text
91d37ad4de7106d5038ed7bffe1e373db65e0f4771865da8975a216e76ed34f3
```

The archive is read directly; do not extract the tar file for normal operation. If your checksum differs, inspect dataset provenance rather than bypassing the checksum check.

## 3. Create the local dataset configuration

```bash
cp config/environments/local/.env.example config/environments/local/.env
nano config/environments/local/.env
```

Set `ROADSENSE_DATASET_ROOT` to an **absolute path** containing the tar file, for example:

```dotenv
ROADSENSE_DATASET_ROOT=/home/your-user/datasets/roadsense
```

The preparatory script reads this file. You do not need to fill the example's empty password entries manually.

## 4. Generate the local credentials, TLS certificate and runtime configuration

```bash
sh tools/prepare_local.sh
```

The script generates `config/environments/local/.env.runtime`, the local MQTT CA/server certificate, broker credentials, and a protected PostgreSQL password file. These files are ignored by Git. It preserves an existing PostgreSQL password on subsequent runs.

**Never commit or publish the generated environment file, certificate private keys or password files.** If the setup script reports a missing archive, check the dataset path and archive filename from Steps 2–3.

## 5. Validate and start the full application

```bash
COMPOSE=(
  docker compose
  --env-file config/environments/local/.env.runtime
  -f infrastructure/compose/local.yaml
)
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" up --build -d --wait \
  mqtt-broker postgres signal-processor road-analyzer api dashboard
```

The `analyzer-migrate` one-shot service runs before the analyzer as part of the Compose dependency chain. The first run downloads base images and builds Python images; later runs reuse the build cache.

Inspect the result:

```bash
"${COMPOSE[@]}" ps -a
"${COMPOSE[@]}" logs --tail=80 mqtt-broker signal-processor road-analyzer postgres api dashboard
```

Expected: broker, database, processor, analyzer, API and dashboard remain running. The migration service completes successfully.

## 6. Check the API and dashboard

```bash
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS http://127.0.0.1:8000/api/v1/status
curl -fsS http://127.0.0.1:8501/_stcore/health
```

The readiness response is `{"status":"ready"}`; Streamlit health responds `ok`. Open **http://127.0.0.1:8501** in a browser. Local API documentation is at **http://127.0.0.1:8000/docs**.

Only the HTTP API and dashboard are published to the host, bound to `127.0.0.1`; MQTT and PostgreSQL stay on internal Compose networks.

## 7. Replay a recorded IMU session

Create a unique run ID, then publish the first 1,536 samples:

```bash
export RUN_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
echo "Run ID: $RUN_ID"

"${COMPOSE[@]}" run --rm --no-deps \
  -e RUN_ID="$RUN_ID" \
  -e MAX_SAMPLES=1536 \
  -e REPLAY_RATE=0 \
  -e BATCH_SIZE=64 \
  sensor-replay
```

The replay is a one-shot command. The MQTT broker and processor/analyzer must remain running. For real-time paced playback, use a positive `REPLAY_RATE`; zero runs as quickly as feasible. To replay all samples, set `MAX_SAMPLES=0`.

## 8. Verify stored results

```bash
curl -fsS "http://127.0.0.1:8000/api/v1/runs/$RUN_ID/features?limit=500"
curl -fsS "http://127.0.0.1:8000/api/v1/runs/$RUN_ID/events?limit=500"
curl -fsS http://127.0.0.1:8000/api/v1/status
```

For the configured Bumpy Gravel reference recording, the 1,536-sample local check produced **19 feature windows and 5 threshold events** with the default 100 mg threshold. Select the new run in the Streamlit dashboard and compare its charts with the API response. Results depend on the exact dataset revision, configured threshold and completeness of the MQTT pipeline.

## 9. Stop and restart safely

```bash
"${COMPOSE[@]}" down
```

This stops containers but retains named volumes for PostgreSQL, MQTT persistence and processor state. To restart, rerun the `up --build -d --wait ...` command from Step 5. **Do not use `down --volumes`** unless you deliberately want to delete persistent local data.

## Common issues

- **Cannot find archive:** verify `ROADSENSE_DATASET_ROOT`, exact filename, and archive hash.
- **Docker image build fails:** check Docker daemon availability and build logs.
- **Port 8000/8501 occupied:** inspect with `ss -ltnp`; stop the conflicting program or adjust the host port variables in `.env.runtime`.
- **Dashboard loads but no data:** check the API readiness, backend logs and whether replay completed.
- **Permission errors:** inspect the private runtime directory and mounted files; avoid making secrets world-readable.
- **Unwanted local Rahti connection:** local mode must use only `local.yaml`, never the Rahti client override.
