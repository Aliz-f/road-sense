# RoadSense Phase 06 — Learn and perform the remote deployment

**Status:** Repository deployment **preparation** only. No VPS or Rahti
system has been inspected, changed, or deployed by the Phase 06 preparation
commit. Nothing in this guide proves a remote deployment works.

The verified Phase 05 complete laptop stack remains the baseline. Phase 06
splits it: one-shot Sensor Replay and Streamlit on personal VPS with Compose;
TLS Mosquitto, one Signal Processor, one Road Analyzer, PostgreSQL/PVC, and
FastAPI on Rahti OpenShift.

> Safety gate: Do NOT run publish, apply, secret generation on target, VPS
> changes, external Routes, firewall/SSH/DNS edits, or incur costs until their
> specific changes are reviewed and explicitly approved. Scripts default to
> plan-only where applicable. No secrets or raw MUHOS archives may be committed.

## 0. Learn the deployment sequence

| Phase | Tool | What it does | Remote change? |
|---|---|---|---|
| Inspect laptop | `tools/phase06_preflight.sh local` | Checks Docker/buildx and working tree | No |
| Inspect VPS | `tools/phase06_preflight.sh vps` **on VPS** | OS, storage, Docker versions | No |
| Inspect Rahti | `tools/phase06_preflight.sh rahti` | Project, quotas, storage and create permissions | No |
| Release | `tools/phase06_publish_images.sh --plan` | Shows versioned registry build/push plan | No |
| Release execute | `... --execute` | Builds + pushes to approved GHCR | **Yes, registry** |
| TLS/credentials | `tools/phase06_prepare_secrets.sh --local-only ...` | Creates protected local keys/passwords | Local files only |
| Render | `tools/phase06_render_rahti.py` | Replaces image placeholders in non-secret manifests | No |
| Rahti secrets | `tools/phase06_rahti.sh secrets --execute` | Creates namespace Secrets | **Yes** |
| Rahti core | `... core --execute` | Creates broker/PostgreSQL and PVCs | **Yes** |
| Rahti migration | `... migrate --execute` | Applies schema migrations once | **Yes** |
| Rahti apps | `... apps --execute` | Starts processor, analyzer and API | **Yes** |
| Rahti routes | `... routes --execute` | OPTIONAL guarded external endpoints | **Yes, public endpoints** |
| VPS | `docker compose ... up -d dashboard` | Starts VPS dashboard, bound to loopback | **Yes** |
| Replay | `docker compose ... run --rm sensor-replay` | Sends MUHOS recording from VPS | **Yes, data delivery** |

The `oc` command is OpenShift's Kubernetes CLI. A Deployment owns and
updates application Pods. A Service gives stable cluster-internal DNS.
A PVC requests persistent storage. A Job runs migrations once. A Secret
provides credentials. A Route can expose a Service outside the cluster.
`rollout status` waits for a Deployment to be healthy.

### Preparation unit checks (no server access)

```sh
python3 -m unittest discover -s tests -p 'test_phase06_preparation.py' -v
for file in tools/phase06_*.sh; do bash -n "$file"; done
python3 -m py_compile tools/phase06_render_rahti.py
```

These checks verify template rendering, immutable image requirements, and
safe placeholder handling. They do not prove that live Rahti accepts the resources.

## 1. Inspect prerequisites without making changes

**Laptop** (repository root):

```sh
./tools/phase06_preflight.sh local
./tests/phase05_e2e.sh
```

The Phase 05 test re-creates the local Compose stack, rotates test credentials
and shuts down the services, but retains named volumes. Run only when no
manual demo is active.

**VPS**, after you have separately connected by SSH:

```sh
./tools/phase06_preflight.sh vps
```

Verify Docker/Compose, x86_64 or chosen image architecture, disk,
private archives, ability to pull registry images, and no unrelated workloads
would be interrupted. Do not install Docker, change SSH/firewall/DNS, or copy
files as part of this inspection.

**Rahti**, on a workstation where `oc` is already installed and logged in:

```sh
export RAHTI_NAMESPACE=REPLACE_ACTUAL_PROJECT_NAME
./tools/phase06_preflight.sh rahti
oc -n "$RAHTI_NAMESPACE" get pods,pvc,deployments
oc -n "$RAHTI_NAMESPACE" get routes
```

Confirm namespace, project quota, PVC storage class, supported image registry
pull credentials, non-root security context (restricted SCC), and Route
passthrough/SSL support. Verify permitted `LoadBalancer` / routing alternatives.
**Rahti MQTT/TLS external network access is not assumed available.**

## 2. Release immutable container images

The published Python images come from the same versioned source used locally.
The broker image comes from `infrastructure/rahti/mosquitto/Dockerfile` and
adds OpenShift arbitrary-UID compatible group permissions.

```sh
# Set the GHCR namespace allowed by your GitHub account/project.
export GHCR_OWNER=REPLACE_OWNER
export RELEASE_PLATFORM=linux/amd64  # change only after checking VPS + Rahti
./tools/phase06_publish_images.sh --plan
```

Review the plan. After explicit approval, log in securely using your own
credential manager (never copy a token into Git or chat), then:

```sh
export ROAD_SENSE_APPROVED=yes
./tools/phase06_publish_images.sh --execute
```

Requires local Docker buildx and authenticated GHCR permission. The script
pushes **six** images tagged with the source Git commit short SHA: sensor,
dashboard, processor, analyzer, API, broker. Record the resulting *manifest
digests* from `docker buildx imagetools inspect`; DO NOT use unpinned tags
in remote manifests. Confirm remote architecture and registry visibility.
For private images configure a scoped OpenShift image pull Secret and a
suitable VPS `docker login`, rather than embedding tokens in manifests.

**PostgreSQL exception:** the local `postgres:16.6-bookworm` image is
not automatically compatible with Rahti's arbitrary non-root UID policy.
The template recommends an OpenShift-oriented PostgreSQL 16 image
(`quay.io/sclorg/postgresql-16-c9s`) **as a candidate only**. Verify it
exists, check its documentation/startup/PVC ownership behavior on your
actual Rahti project, pin its immutable digest, and confirm all PostgreSQL
migrations work before claiming readiness.

## 3. Create local secrets, never store them in Git

This example creates a private demonstration CA and broker cert with SANs for
`mqtt-broker` and the approved external MQTT route hostname. This is NOT
a public-trust CA. The VPS must trust the generated `ca.crt`.

```sh
# On a trusted laptop, AFTER choosing the actual approved MQTT route hostname:
./tools/phase06_prepare_secrets.sh --local-only \
  mqtt.REPLACE_APPROVED_HOST /private/roadsense-phase06-secrets
```

The command generates a CA key, broker key/certificate, secure random MQTT
and PostgreSQL passwords, and a Mosquitto hashed password file. Inspect
permissions; keep the directory private, **outside Git**, and back it up
securely. Never transfer `ca.key` to Rahti or the VPS.

The broker credential username is currently fixed to `roadsense-remote` in
its ACL/Secret command. Do not change just the Secret username without
changing the ACL. A more elaborate environment can use separate least-
privilege MQTT clients, but that requires an additional authenticated design.

## 4. Render manifests without contacting Rahti

```sh
cp infrastructure/rahti/images.env.example infrastructure/rahti/images.env
# Replace with FIVE correct image@sha256 digests, including PostgreSQL.
python3 tools/phase06_render_rahti.py \
  --settings infrastructure/rahti/images.env \
  --output-dir infrastructure/rahti/generated
```

Review rendered YAML: image digests, PVC sizes (default Postgres 5Gi,
Mosquitto 1Gi), resource requests/limits, selectors, ConfigMap values,
NetworkPolicy, and the mounted credential paths. No passwords are in YAML.

`core.yaml` creates the *internal-only* infrastructure. `migrate.yaml`
defines the schema-migration Job. `apps.yaml` defines processor/analyzer/API.
No public routes are included unless specifically requested below.

If the selected Rahti account uses a particular storage class, check
`oc get storageclass` and configure it explicitly after review. If a
PostgreSQL image uses a different data path, update the image/mount together.
A wrong image or non-writable PVC can prevent deployment.

## 5. Deploy in deliberate stages (requires approval)

**These commands create remote resources and are intentionally NOT executed
during preparation.** Once approved, export the namespace and local secret
directory paths on the machine where `oc` is authenticated:

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

The script requires the currently selected `oc project -q` to **match**
`RAHTI_NAMESPACE`. Each execution stops on the first error; do not keep
proceeding after failure. `core` waits for database/broker rollout; migration
waits for the Job to complete; `apps` is blocked until migrations finish.

Check private API using a temporary localhost-only port forward:

```sh
oc -n "$RAHTI_NAMESPACE" port-forward service/api 18000:8000
# In a separate laptop terminal:
curl -fsS http://127.0.0.1:18000/health/ready
```

Port-forward is temporary and not equivalent to a public Route.

For troubleshooting:

```sh
oc -n "$RAHTI_NAMESPACE" get pods,pvc,deployments,jobs
oc -n "$RAHTI_NAMESPACE" describe pod POD_NAME
oc -n "$RAHTI_NAMESPACE" logs job/roadsense-migrate-v1
oc -n "$RAHTI_NAMESPACE" logs deployment/road-analyzer --tail=70
```

Sanitize logs before sharing. Check actual writable data mounts and verify
that PostgreSQL and Mosquitto retain state across isolated Pod restarts.
Take backups before intentionally interrupting data or changing storage.

## 6. Optional cross-environment HTTPS and MQTT routes

**DO NOT treat this as an automatic step**. Before publishing any Route,
inspect Rahti's current ingress documentation and test supported endpoints
against your actual project.

- MQTT: requires **TCP/TLS passthrough with SNI**; OpenShift HTTPS Routes
  generally use external port **443**, even when the internal Service is 8883.
  The certificate needs the external hostname in SAN. Confirm your Rahti
  router actually supports this MQTT passthrough behavior and a verified
  source-IP allowlist, or choose an explicitly approved alternative.
- FastAPI: example edge-terminated HTTPS Route. Since the application has no
  login, allow requests **only from the approved VPS source IP** (or use a
  verified VPN/authenticated gateway). Test unauthorized traffic is rejected.
- Both routes default to a source allowlist annotation. Its enforcement and
  actual VPS egress IP **must be verified**. Do not assume annotations alone
  provide sufficient security. PostgreSQL NEVER gets a public Route.

Add real, reviewed values to the ignored `images.env`:

```dotenv
MQTT_PUBLIC_HOST=mqtt.REPLACE_APPROVED_HOST
API_PUBLIC_HOST=api.REPLACE_APPROVED_HOST
VPS_EGRESS_CIDR=REPLACE_VPS_PUBLIC_IP/32
```

Render routes locally:

```sh
python3 tools/phase06_render_rahti.py \
  --settings infrastructure/rahti/images.env \
  --output-dir infrastructure/rahti/generated --include-routes
```

Only **after a separate explicit approval for exposing both endpoints**:

```sh
export ROAD_SENSE_APPROVED=yes
export ROAD_SENSE_PUBLIC_ENDPOINT_APPROVED=yes
./tools/phase06_rahti.sh routes --execute
```

Verify from the VPS using trusted TLS and domain/SNI. Test from an unapproved
network that neither API nor broker is accessible. The API ingress NetworkPolicy is deliberately fail-closed: it only allows\ntraffic from namespaces labeled `network.openshift.io/policy-group=ingress`.\nConfirm this selector matches Rahti's actual router namespace before applying\nthe Route. If not, adjust policy ONLY after inspecting the cluster topology,\nand do not allow unrestricted API access.\n\nIf IP whitelisting fails,
**disable the Route immediately** and switch to a verified private alternative.
Never disable TLS verification.

## 7. Prepare VPS Compose without public dashboard

Only after explicit VPS approval, copy the deployment files to the VPS and
put the MUHOS archives in a private readable directory; no archive enters Git.
Copy ONLY the CA **certificate** (not the CA private key).

```sh
cd infrastructure/vps
cp .env.example .env
chmod 600 .env
# Edit .env with 2 pinned images, real broker DNS + port 443 (if Route),
# broker username/password and CA path, verified HTTPS API URL, dataset path.
docker compose --env-file .env -f compose.yaml config --quiet
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d --wait dashboard
docker compose --env-file .env -f compose.yaml ps
```

Streamlit binds ONLY VPS loopback `127.0.0.1:8501`. From your laptop:

```sh
ssh -L 8501:127.0.0.1:8501 USER@VPS_HOST
# Then open http://127.0.0.1:8501 in your laptop browser.
```

The VPS dashboard calls `API_INTERNAL_URL=https://...` from **inside its
container**; verify HTTPS certificate trust and Rahti ingress policy. If
your VPS egress IP changes, the API Route allowlist will need updating.

## 8. Full remote end-to-end data trace

Check broker/API connectivity first. In the VPS Compose directory:

```sh
export RUN_ID="$(python3 -c 'import uuid; print(uuid.uuid4())')"
docker compose --env-file .env -f compose.yaml run --rm \
  -e RUN_ID="$RUN_ID" sensor-replay
```

The script publishes raw QoS1 batches and then a run-complete message. Record
`RUN_ID`, replay logs, Rahti broker/processor/analyzer logs, and API results.
A deterministic **1,536-sample Bumpy Gravel** demonstration is expected to
produce **19 feature windows and 5 threshold events** using the default rule.
These expectations are based on the local reference, **not remote test evidence**.

From the VPS (once API Route approved and available):

```sh
curl -fsS "https://API_APPROVED_HOST/health/ready"
curl -fsS "https://API_APPROVED_HOST/api/v1/runs/$RUN_ID/features?limit=500"
curl -fsS "https://API_APPROVED_HOST/api/v1/runs/$RUN_ID/events?limit=500"
```

The final condition is seeing real source data in the VPS Streamlit dashboard
via the Rahti API. Check QoS duplicates, unique run IDs, pending event outbox,
broker restart, analyzer restart and data persistence. **Do not run destructive
failure tests until a backup and rollback have been confirmed.**

## 9. Rollback and repeatability

- **VPS:** restore previous pinned `DASHBOARD_IMAGE` / `SENSOR_IMAGE` in
  the protected `.env`. Recreate the dashboard after approval. Feeder is
  explicitly one-shot and must not replay automatically on reboot.
- **Rahti:** `oc -n "$RAHTI_NAMESPACE" rollout history deployment/api`
  then, if safe, `oc -n "$RAHTI_NAMESPACE" rollout undo deployment/api`.
  Repeat selectively for processor/analyzer/broker. Record the exact prior
  image digests before changing them.
- **Database:** never assume a migration is reversible. Use a tested backup
  and restore plan; never delete PVCs to roll back code.
- **Routes:** withdraw unapproved or insecure public Routes promptly, without
  deleting database/broker storage.
- **Secrets:** never print credentials, commit .env files, or paste tokens.

## 10. Work remaining before Phase 06 can be called complete

- [ ] Verify Phase 05 local tests on final merged commit.
- [ ] Inspect real VPS and Rahti project/quota/storage/permissions.
- [ ] Verify every registry image digest including PostgreSQL candidate.
- [ ] Verify Mosquitto and Postgres run under Rahti restricted SCC + PVCs.
- [ ] Agree and test TLS passthrough/secure external access route solution.
- [ ] Approve and execute registry publish, Rahti deploy and VPS deploy stages.
- [ ] Verify end-to-end remote telemetry, restart/persistence, backups/rollback.
- [ ] Record sanitized remote evidence in a Phase 06 implementation report.

This guide is an educational deployment runbook, **not a claim that remote
infrastructure is deployed**.
