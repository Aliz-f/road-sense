# Distributed deployment — laptop + CSC Rahti (OpenShift)

This deployment keeps the MQTT broker, Signal Processor, Road Analyzer, PostgreSQL and FastAPI inside a **private Rahti namespace**. Your Linux laptop runs only Sensor Replay and Streamlit. Two authenticated `oc port-forward` sessions connect laptop loopback ports to private `ClusterIP` Services. No public Route, NodePort, LoadBalancer or VPS is required.

> These instructions are for an existing authorized Rahti project. They create or update workloads and persistent volumes, and publish images to a container registry. Check your project's quotas, credentials, permissions and course policies first.

## 1. Prepare the machine and dataset

Install `oc`, Docker with Compose v2 and buildx, Python 3, OpenSSL and Git. Have the original `Bumpy Gravel - imu.tar` available at a private absolute path. Complete Steps 2–4 of [local deployment](local-deployment.md) to create the **local** dataset configuration and the `config/environments/local/.env.runtime` file; the laptop clients reuse it for provenance and replay settings.

Verify:

```bash
oc version --client
docker compose version
docker buildx version
./tools/preflight.sh local
```

## 2. Authenticate with Rahti and verify project resources

Log into CSC Rahti using the current instructions and your own credentials. Select the *existing* project you are allowed to use:

```bash
oc whoami
oc projects
oc project YOUR_EXISTING_RAHTI_PROJECT
export RAHTI_NAMESPACE="$(oc project -q)"
./tools/preflight.sh rahti
oc -n "$RAHTI_NAMESPACE" get pods,pvc,deployments,resourcequota
oc get storageclass
```

Confirm available CPU, RAM and persistent storage, the `rahti-restricted-v2` SCC / local seccomp profile required by the manifests, permission to create Secrets/Deployments/Jobs/PVCs, and `pods/portforward` access. A project's resource limits may reject container CPU requests below **50m**; the MQTT broker init-container is configured for 50m CPU. A PVC can be `Pending` under `WaitForFirstConsumer` until its Pod is created.

## 3. Publish runtime images to GHCR

The Rahti deployment requires these four images: `mqtt-broker`, `signal-processor`, `road-analyzer`, `api`. The script publishes only after an explicit approval flag, and requires tracked Git files to be committed.

```bash
export GHCR_OWNER=YOUR_GITHUB_USERNAME
export RELEASE_PLATFORM=linux/amd64
./tools/publish_images.sh --plan
```

Create a **GitHub Personal Access Token (classic)** with `write:packages` and authenticate securely:

```bash
read -rsp 'GitHub token: ' GHCR_TOKEN; echo
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_OWNER" --password-stdin
unset GHCR_TOKEN
```

After reviewing the plan:

```bash
export ROAD_SENSE_APPROVED=yes
./tools/publish_images.sh --execute
```

The publisher builds `--target runtime` for the three Python images. This matters: their Dockerfiles also contain `test` stages, and building the default final stage would start unit tests instead of the application.

Record the immutable `sha256` image index digests printed by `docker buildx imagetools inspect`. In addition, select and verify an **OpenShift arbitrary-UID-compatible PostgreSQL** image, for example a tested PostgreSQL 16 `quay.io/sclorg` image, and record its digest.

**GHCR access:** the cluster needs access to all four packages. You can make the packages public only if you are comfortable with anonymous downloads, or create a Rahti image-pull Secret for private images and attach it to the ServiceAccount. Docker login on the laptop alone does not grant Rahti registry access.

## 4. Generate broker certificates and protected credentials

Use an absolute directory **outside** this repository:

```bash
export RAHTI_SECRET_DIR="$HOME/.local/share/roadsense-rahti-secrets"
./tools/prepare_rahti_secrets.sh --local-only localhost "$RAHTI_SECRET_DIR"
python3 tools/validate_secrets.py "$RAHTI_SECRET_DIR"
```

This creates a private CA, broker certificate with `localhost` and `mqtt-broker` DNS names, MQTT credentials and a PostgreSQL password. Keep the CA private key on the laptop and never put passwords or keys into Git. Do **not** regenerate these files when redeploying an existing Rahti database/broker: the services and laptop clients must keep using the matching credentials and CA.

## 5. Pin images and render Rahti manifests

```bash
cp infrastructure/rahti/images.env.example infrastructure/rahti/images.env
chmod 600 infrastructure/rahti/images.env
nano infrastructure/rahti/images.env
```

Replace all five examples with exact verified `name@sha256:...` references:

```dotenv
BROKER_IMAGE=ghcr.io/YOUR_GITHUB_USERNAME/road-sense-mqtt-broker@sha256:ACTUAL_64_HEX_DIGEST
PROCESSOR_IMAGE=ghcr.io/YOUR_GITHUB_USERNAME/road-sense-signal-processor@sha256:ACTUAL_64_HEX_DIGEST
ANALYZER_IMAGE=ghcr.io/YOUR_GITHUB_USERNAME/road-sense-road-analyzer@sha256:ACTUAL_64_HEX_DIGEST
API_IMAGE=ghcr.io/YOUR_GITHUB_USERNAME/road-sense-api@sha256:ACTUAL_64_HEX_DIGEST
POSTGRES_IMAGE=quay.io/sclorg/postgresql-16-c9s@sha256:ACTUAL_64_HEX_DIGEST
```

Do not literally use the placeholders. Render:

```bash
python3 tools/render_rahti.py \
  --settings infrastructure/rahti/images.env \
  --output-dir infrastructure/rahti/generated
```

Inspect the generated `core.yaml`, `migrate.yaml` and `apps.yaml`, including storage, resource requests, images, ConfigMaps, Secrets and network policies:

```bash
oc -n "$RAHTI_NAMESPACE" apply --dry-run=server \
  -f infrastructure/rahti/generated/core.yaml
```

## 6. Deploy in order

```bash
export RAHTI_NAMESPACE="$(oc project -q)"
export ROAD_SENSE_APPROVED=yes
export RAHTI_SECRET_DIR="$HOME/.local/share/roadsense-rahti-secrets"

./tools/deploy_rahti.sh secrets --execute
./tools/deploy_rahti.sh core --execute
oc -n "$RAHTI_NAMESPACE" get deployments,pods,pvc,services

./tools/deploy_rahti.sh migrate --execute
oc -n "$RAHTI_NAMESPACE" get jobs

./tools/deploy_rahti.sh apps --execute
./tools/verify_rahti.sh rahti
```

The migration Job must complete before applying the application workloads. The migration identifier depends on the analyzer image digest; if you change the analyzer image and rerender manifests, run the migration stage again. Do not remove PVCs to retry a failed deployment.

Expected after rollout: `postgres`, `mqtt-broker`, `signal-processor`, `road-analyzer`, `api` each show `1/1` ready. Three persistent claims (PostgreSQL 5Gi, MQTT 1Gi, processor state 1Gi) should be bound.

**Existing deployment caution:** this standalone distribution is intended for a **fresh PostgreSQL database**. If you reuse a database created by an earlier release whose migration filenames differ, reconcile migration records and checksums before deployment. Never delete an existing database or PVC just to make a renamed migration pass.

## 7. Start the laptop's two private tunnels

Open two separate foreground terminals and keep them running.

**Terminal A — MQTT/TLS:**

```bash
export RAHTI_NAMESPACE="$(oc project -q)"
oc -n "$RAHTI_NAMESPACE" port-forward --address 127.0.0.1 \
  service/mqtt-broker 18883:8883
```

**Terminal B — FastAPI:**

```bash
export RAHTI_NAMESPACE="$(oc project -q)"
oc -n "$RAHTI_NAMESPACE" port-forward --address 127.0.0.1 \
  service/api 18000:8000
```

**Terminal C — verify both endpoints:**

```bash
export RAHTI_SECRET_DIR="$HOME/.local/share/roadsense-rahti-secrets"
curl -fsS http://127.0.0.1:18000/health/ready

openssl s_client -connect 127.0.0.1:18883 \
  -servername localhost -verify_hostname localhost \
  -CAfile "$RAHTI_SECRET_DIR/ca.crt" \
  -verify_return_error -brief </dev/null
```

Look for `{"status":"ready"}` and `Verification: OK`. The TLS handshake alone does not verify MQTT username/password login.

## 8. Configure laptop-only clients

Stop an existing local Compose stack without deleting volumes, if it is running:

```bash
docker compose --env-file config/environments/local/.env.runtime \
  -f infrastructure/compose/local.yaml down
```

Copy the distributed client template:

```bash
cp infrastructure/compose/rahti-client.env.example infrastructure/compose/rahti-client.env
chmod 600 infrastructure/compose/rahti-client.env
nano infrastructure/compose/rahti-client.env
```

Set `RAHTI_MQTT_FORWARD_PORT=18883`, `RAHTI_API_FORWARD_PORT=18000`, `RAHTI_MQTT_USERNAME=roadsense-remote`, `RAHTI_MQTT_PASSWORD` to the **newline-free value** in `$RAHTI_SECRET_DIR/mqtt-password`, and `MQTT_RUNTIME_DIR` to the **absolute** `$RAHTI_SECRET_DIR`. The password file is protected: never display or share it.

```bash
COMPOSE=(
  docker compose
  --env-file config/environments/local/.env.runtime
  --env-file infrastructure/compose/rahti-client.env
  -f infrastructure/compose/local.yaml
  -f infrastructure/compose/rahti-client.yaml
)
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build sensor-replay dashboard
"${COMPOSE[@]}" up -d --no-deps dashboard
```

Check `curl -fsS http://127.0.0.1:8501/_stcore/health` and open **http://127.0.0.1:8501**. The dashboard reads from the private API through localhost port `18000`.

**Docker Desktop on Linux:** the client override uses `network_mode: host`. In Docker Desktop, enable **Settings → Resources → Network → Enable host networking**, apply the setting, and recreate the dashboard. Without that setting, a Streamlit health check *inside* the container can pass while the laptop browser still receives `connection refused`. If needed, use the native Linux Docker Engine and rebuild clients there.

## 9. Replay data end to end

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

The broker receives MQTT/TLS batches from the laptop through port `18883`; processor and analyzer run in Rahti, write to PostgreSQL, and FastAPI exposes the results to the laptop dashboard.

```bash
curl -fsS "http://127.0.0.1:18000/api/v1/runs/$RUN_ID/features?limit=500"
curl -fsS "http://127.0.0.1:18000/api/v1/runs/$RUN_ID/events?limit=500"
curl -fsS http://127.0.0.1:18000/api/v1/status
```

For the configured 1,536-sample Bumpy Gravel recording, the local reference produced 19 windows and 5 threshold events. Verify actual remote outputs and view the matching run in Streamlit.

## 10. Monitoring, recovery and shutdown

```bash
oc -n "$RAHTI_NAMESPACE" get deployments,pods,pvc,services,jobs
oc -n "$RAHTI_NAMESPACE" logs deployment/signal-processor --tail=80
oc -n "$RAHTI_NAMESPACE" logs deployment/road-analyzer --tail=80
oc -n "$RAHTI_NAMESPACE" logs deployment/api --tail=80
"${COMPOSE[@]}" logs --tail=80 dashboard
```

For a failed Pod, inspect `oc describe pod POD_NAME` and sorted events. `ErrImagePull` with `unauthorized` means Rahti lacks GHCR pull access. `FailedCreate` complaining about minimum CPU means adjust the relevant container request to the cluster minimum (at least 50m in the observed namespace). `CrashLoopBackOff` requires `oc logs ... --previous`; ensure application images have **runtime** entrypoints, not the unit-test entrypoint.

Stop only the laptop client and the two foreground tunnels when finished:

```bash
"${COMPOSE[@]}" stop dashboard
# Press Ctrl-C in each oc port-forward terminal.
```

Rahti workloads remain running and using storage. To stop the remote deployments intentionally, scale them down only after understanding persistent sessions and data recovery. Never delete PVCs or use `down --volumes` casually.
