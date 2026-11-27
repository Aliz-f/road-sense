# RoadSense Phase 06 — laptop + private CSC Rahti

**Status:** repository preparation only. No Rahti resource was inspected,
changed or deployed while preparing this guide. The complete Phase 05 laptop
stack remains the verified baseline.

The former VPS/public-endpoint plan is abandoned. Current Phase 06 deploys
Mosquitto, Signal Processor, Road Analyzer, PostgreSQL and FastAPI to Rahti.
Sensor Replay and Streamlit stay on the Linux laptop. Two authenticated,
loopback-only `oc port-forward` sessions connect the laptop clients to private
ClusterIP Services.

> Approval gate: do not publish images, create credentials on a target, apply
> manifests or change Rahti until the exact action is reviewed and approved.
> Never commit credentials, private keys, generated manifests or MUHOS archives.

## 1. Offline preparation checks

From the repository root:

```sh
./tools/phase06_preflight.sh local
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml config --quiet
python3 -m unittest discover -s tests -p 'test_phase06_preparation.py' -v
for file in tools/phase06_*.sh; do bash -n "$file"; done
python3 -m py_compile tools/phase06_render_rahti.py tools/phase06_validate_secret_files.py
```

For offline validation of the laptop client merge, copy the example to a
temporary protected file, replace its placeholders, and run:

```sh
docker compose \
  --env-file config/environments/local/.env.phase02 \
  --env-file infrastructure/compose/rahti-client.env \
  -f infrastructure/compose/local.compose.yaml \
  -f infrastructure/compose/rahti-client.compose.yaml config --quiet
```

These checks do not prove Rahti accepts the manifests or that port-forward
traffic is permitted by the live cluster network.

## 2. Inspect the existing Rahti project

On the laptop where `oc` is installed and authenticated:

```sh
export RAHTI_NAMESPACE=REPLACE_ACTUAL_EXISTING_PROJECT
./tools/phase06_preflight.sh rahti
oc -n "$RAHTI_NAMESPACE" get pods,pvc,deployments,networkpolicies
```

Confirm the selected `oc project -q` exactly matches the namespace, and verify
quota, RWO storage, arbitrary-UID/SCC behavior, seccomp profile, registry pull
credentials and permissions. Do not install tools or create resources during
inspection. Recheck CSC documentation immediately before deployment because
cluster policy changes.

## 3. Publish immutable Rahti images — approval required

The laptop Sensor Replay and Streamlit keep using locally built images. Rahti
needs processor, analyzer, API and arbitrary-UID-compatible Mosquitto images:

```sh
export GHCR_OWNER=REPLACE_OWNER
export RELEASE_PLATFORM=linux/amd64  # verify against Rahti first
./tools/phase06_publish_images.sh --plan
```

After explicit approval and secure registry login:

```sh
export ROAD_SENSE_APPROVED=yes
./tools/phase06_publish_images.sh --execute
```

Record manifest digests. PostgreSQL is separate: verify an OpenShift-compatible
PostgreSQL 16 image, startup variables, arbitrary UID and PVC path on Rahti,
then pin its digest. The example image is a candidate, not verified evidence.

## 4. Prepare private credentials locally

Generate a private CA, broker certificate, MQTT credential and PostgreSQL
password in a protected directory outside Git. `localhost` is the MQTT name
seen by Sensor Replay through the laptop loopback forward:

```sh
./tools/phase06_prepare_secrets.sh --local-only localhost \
  /private/roadsense-phase06-secrets
```

The broker certificate contains `DNS:localhost` and `DNS:mqtt-broker`. Sensor
Replay mounts `ca.crt` and verifies the former; Rahti internal clients verify
the latter. Keep `ca.key` only on the trusted laptop. Never print or paste the
generated passwords.

## 5. Render private manifests locally

```sh
cp infrastructure/rahti/images.env.example infrastructure/rahti/images.env
# Replace all five values with verified image@sha256 digests.
python3 tools/phase06_render_rahti.py \
  --settings infrastructure/rahti/images.env \
  --output-dir infrastructure/rahti/generated
```

Review `core.yaml`, `migrate.yaml` and `apps.yaml`: exact digests, resources,
PVC sizes/mounts, probes, ConfigMaps, Secrets references, Recreate strategies
and NetworkPolicies. The baseline has only ClusterIP Services. It has no Route,
LoadBalancer, NodePort, public hostname or special LoadBalancer node selector.

`core` creates broker/PostgreSQL and PVCs. `migrate` creates a fresh,
release-bound migration Job with advisory locking and checksums. `apps` creates
processor/analyzer/API; the processor has a dedicated RWO journal PVC and must
replay it before readiness.

## 6. Deploy in guarded stages — approval required

Only after review and explicit approval:

```sh
export RAHTI_NAMESPACE=REPLACE_ACTUAL_EXISTING_PROJECT
export PHASE06_SECRET_DIR=/private/roadsense-phase06-secrets
export ROAD_SENSE_APPROVED=yes

./tools/phase06_rahti.sh secrets --execute
./tools/phase06_rahti.sh core --execute
./tools/phase06_rahti.sh migrate --execute
./tools/phase06_rahti.sh apps --execute
./tools/phase06_rahti.sh status --execute
```

The script refuses a namespace mismatch and stops on errors. `core` checks
Secrets and rollout; `migrate` waits for completion; `apps` requires the exact
migration marker. PostgreSQL never receives an external Service.

Troubleshoot with sanitized output from `oc get`, `oc describe` and scoped
`oc logs`. Verify actual PVC write behavior, arbitrary UID, seccomp policy and
image pulls rather than inferring success from local rendering.

## 7. Start private laptop forwards

Use separate terminals and keep both commands in the foreground:

```sh
oc -n "$RAHTI_NAMESPACE" port-forward --address 127.0.0.1 \
  service/mqtt-broker 18883:8883
```

```sh
oc -n "$RAHTI_NAMESPACE" port-forward --address 127.0.0.1 \
  service/api 18000:8000
```

Check the private API locally:

```sh
curl -fsS http://127.0.0.1:18000/health/ready
```

These forwards require the user's authenticated `oc` session, listen only on
laptop loopback, disappear when stopped, and create no Rahti public endpoint.
The API has no application login, so do not change `--address` to a LAN/public
address.

## 8. Run laptop Sensor Replay and Streamlit

Create a protected, ignored client environment:

```sh
cp infrastructure/compose/rahti-client.env.example \
  infrastructure/compose/rahti-client.env
chmod 600 infrastructure/compose/rahti-client.env
# Set MQTT_RUNTIME_DIR to PHASE06_SECRET_DIR and copy the newline-free MQTT
# password value into RAHTI_MQTT_PASSWORD without printing it to logs.
```

Validate the merged configuration, then start only the dashboard without its
local API dependency:

```sh
docker compose \
  --env-file config/environments/local/.env.phase02 \
  --env-file infrastructure/compose/rahti-client.env \
  -f infrastructure/compose/local.compose.yaml \
  -f infrastructure/compose/rahti-client.compose.yaml config --quiet

docker compose \
  --env-file config/environments/local/.env.phase02 \
  --env-file infrastructure/compose/rahti-client.env \
  -f infrastructure/compose/local.compose.yaml \
  -f infrastructure/compose/rahti-client.compose.yaml up -d --no-deps dashboard
```

Open `http://127.0.0.1:8501`. Run one replay with a recorded run ID:

```sh
export RUN_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
docker compose \
  --env-file config/environments/local/.env.phase02 \
  --env-file infrastructure/compose/rahti-client.env \
  -f infrastructure/compose/local.compose.yaml \
  -f infrastructure/compose/rahti-client.compose.yaml run --rm --no-deps \
  -e RUN_ID="$RUN_ID" sensor-replay
```

Host networking is Linux-specific and used only by these two client
containers. It lets them reach the loopback forwards while reusing the tested
service images, mounts, read-only filesystems and application configuration.
No laptop broker, processor, analyzer, database or API is started in this mode.

Verify the run through the forwarded API and dashboard. Expected window/event
counts from local reference data are comparison targets, not remote evidence.

## 9. Live acceptance and recovery

Record sanitized evidence for:

- exact image digests, namespace and successful rollouts;
- one run_id from replay through features/events/API/dashboard;
- MQTT authentication failure with wrong credentials and certificate failure
  with an untrusted CA;
- broker durable session/Mosquitto PVC recovery;
- PostgreSQL data retention;
- processor journal recovery preserving source anchor, sequence/sample IDs and
  contiguous windows;
- analyzer duplicate handling and pending outbox state;
- backups and rollback commands before disruptive tests.

Stop the dashboard and foreground forwards after the demo. Never use
`down --volumes` against retained local evidence, and never delete Rahti PVCs
as rollback.

## 10. Remaining prerequisites

- [ ] Authenticated access to the real Rahti namespace.
- [ ] Verified quota, storage class, SCC/seccomp and NetworkPolicy behavior.
- [ ] Approved registry publishing and verified immutable image digests.
- [ ] Verified OpenShift PostgreSQL image and PVC data path.
- [ ] Approved staged deployment and Secret creation.
- [ ] Live laptop-to-Rahti TLS/authenticated trace and restart tests.
- [ ] Sanitized Phase 06 implementation evidence.

Do not claim Phase 06 complete and do not start Phase 07 until these live checks
pass.
