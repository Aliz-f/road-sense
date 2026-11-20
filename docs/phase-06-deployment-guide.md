# RoadSense Phase 06 — Learn and perform the remote deployment

**Status:** Repository deployment **preparation** only. No VPS or Rahti
system has been inspected, changed, or deployed by the Phase 06 preparation
commit. Nothing in this guide proves a remote deployment works.

The verified Phase 05 complete laptop stack remains the baseline. Phase 06
splits it: one-shot Sensor Replay and Streamlit on personal VPS with Compose;
TLS Mosquitto, one Signal Processor, one Road Analyzer, PostgreSQL/PVC, and
FastAPI on Rahti OpenShift.

> Safety gate: Do NOT run publish, apply, secret generation on target, VPS
> changes, external endpoints, firewall/SSH/DNS edits, or incur costs until their
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
| Rahti migration | `... migrate --execute` | Creates a fresh release-bound migration Job | **Yes** |
| Rahti apps | `... apps --execute` | Starts processor, analyzer and API | **Yes** |
| Rahti API Route | `... routes --execute` | OPTIONAL guarded HTTPS API | **Yes, public endpoint** |
| Rahti MQTT LoadBalancer | `... mqtt-external --execute` | OPTIONAL approved raw-TCP MQTT/TLS | **Yes, public endpoint** |
| VPS | `docker compose ... up -d dashboard` | Starts VPS dashboard, bound to loopback | **Yes** |
| Replay | `docker compose ... run --rm sensor-replay` | Sends MUHOS recording from VPS | **Yes, data delivery** |

The `oc` command is OpenShift's Kubernetes CLI. A Deployment owns and
updates application Pods. A Service gives stable cluster-internal DNS.
A PVC requests persistent storage. A Job runs one migration execution. A Secret
provides credentials. A Route can expose a Service outside the cluster.
An approved LoadBalancer Service provides the raw TCP endpoint Routes cannot.
`rollout status` waits for a Deployment to be healthy.

### Preparation unit checks (no server access)

```sh
python3 -m unittest discover -s tests -p 'test_phase06_preparation.py' -v
for file in tools/phase06_*.sh; do bash -n "$file"; done
python3 -m py_compile tools/phase06_render_rahti.py
python3 -m py_compile tools/phase06_validate_secret_files.py
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
pull credentials, non-root security context (`rahti-restricted-v2`), HTTPS
Route support, and whether CSC Service Desk has assigned this project a
LoadBalancer ingress IP. **Rahti MQTT/TLS external access is unavailable until
that separate approval exists.**

Current CSC workload-security documentation says Rahti assigns an arbitrary
project UID and fsGroup and that the restricted SCC defaults to the local
`rahti-custom-seccomp.json` profile. The manifests request that exact profile;
do not replace it with `RuntimeDefault`. Recheck the
[CSC workload security guide](https://docs.csc.fi/cloud/rahti/configurations/workload-security/)
immediately before deployment because cluster policy can change.

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
`mqtt-broker` and the DNS name mapped to the approved LoadBalancer IP. This is NOT
a public-trust CA. The VPS must trust the generated `ca.crt`.

```sh
# On a trusted laptop, AFTER choosing the actual approved MQTT DNS hostname:
./tools/phase06_prepare_secrets.sh --local-only \
  mqtt.REPLACE_APPROVED_HOST /private/roadsense-phase06-secrets
```

The command generates a CA key, broker key/certificate, secure random MQTT
and PostgreSQL passwords, and a Mosquitto hashed password file. Inspect
permissions; keep the directory private, **outside Git**, and back it up
securely. Never transfer `ca.key` to Rahti or the VPS.

Password files are deliberately newline-free. Kubernetes preserves Secret
bytes: PostgreSQL receives the same `password` key as an environment value,
while analyzer/API/migration mount that key as a file and reject embedded line
breaks. `phase06_validate_secret_files.py` checks this without printing values.

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
Mosquitto 1Gi, processor state 1Gi), resource requests/limits, selectors, ConfigMap values,
NetworkPolicy, and the mounted credential paths. No passwords are in YAML.

`core.yaml` creates the *internal-only* infrastructure. `migrate.yaml`
defines a generate-name schema-migration Job tied to the analyzer image digest.
Each execution creates a fresh Job; PostgreSQL advisory locking and immutable
migration checksums make concurrent/repeated execution safe. The apps stage
requires the matching successful migration marker. `apps.yaml` defines
processor/analyzer/API. The processor uses a Recreate strategy and its own RWO
PVC because acknowledged active-run input must survive Pod replacement.
No public resource is included unless specifically requested below.

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
oc -n "$RAHTI_NAMESPACE" get jobs -l app=roadsense-migrate --sort-by=.metadata.creationTimestamp
oc -n "$RAHTI_NAMESPACE" logs job/REPLACE_GENERATED_MIGRATION_JOB
oc -n "$RAHTI_NAMESPACE" logs deployment/road-analyzer --tail=70
```

Sanitize logs before sharing. Mosquitto has an init container that performs a
create/remove check on `/mosquitto/data` using the same arbitrary UID/fsGroup
model before the broker starts. This validates permissions but not persistence;
verify queued QoS 1 messages and `mosquitto.db` survive an isolated Pod restart.
CSC documents Rahti PVCs as `ReadWriteOnce` and currently uses `standard-csi`;
confirm the real project before setting a storage class. See
[CSC persistent storage](https://docs.csc.fi/cloud/rahti/usage/storage/persistent/).
Check that PostgreSQL retains state too.
The Signal Processor must not become ready until its journal has replayed.
During an approved restart test, interrupt an active replay after at least one
acknowledged batch, replace the processor Pod, and verify the next feature keeps
the original `source_start`, `window_index`, and sample count. The processor
PVC contains source-derived payloads and must be protected/backed up accordingly.
Take backups before intentionally interrupting data or changing storage.

## 6. Optional external HTTPS API and raw-TCP MQTT

**DO NOT treat this as an automatic step.** CSC documents OpenShift Routes as
HTTP/HTTPS only; a TLS-passthrough Route is therefore not a supported raw-MQTT
transport. RoadSense uses two different, separately approved mechanisms:

- FastAPI: an edge-terminated HTTPS Route restricted to the verified VPS
  source IP. The application has no login, so replace this with an approved
  authenticated/private gateway if the allowlist cannot be proven.
- MQTT: a `LoadBalancer` Service on external TCP port `30883`, forwarding to
  broker port `8883`. CSC Service Desk must first approve a project ingress IP.
  The manifest sets `allocateLoadBalancerNodePorts: false` because Rahti does
  not provide NodePorts, uses the documented 30000–35000 port range, and sets
  `externalTrafficPolicy: Local` plus the documented broker node selector so
  the VPS source IP remains usable by NetworkPolicy.

See [CSC LoadBalancer Service documentation](https://docs.csc.fi/cloud/rahti/configurations/loadbalancer-service/).
Do not apply `mqtt-external.yaml` until the actual project has an assigned IP,
the broker Pod can schedule on a `rahti.csc.fi/local-load-balancer` node, and
the effect on project quota/cost has been approved. MQTT still requires its
own TLS certificate and strong authentication; IP filtering is only a second
layer. PostgreSQL never receives a public endpoint.

Add reviewed non-secret values to the ignored `images.env`:

```dotenv
API_PUBLIC_HOST=api.REPLACE_APPROVED_HOST
VPS_EGRESS_CIDR=REPLACE_VPS_PUBLIC_IP/32
```

Render both optional external manifests locally:

```sh
python3 tools/phase06_render_rahti.py \
  --settings infrastructure/rahti/images.env \
  --output-dir infrastructure/rahti/generated --include-external
```

After separate owner approval, the API Route can be applied independently:

```sh
export ROAD_SENSE_APPROVED=yes
export ROAD_SENSE_PUBLIC_ENDPOINT_APPROVED=yes
./tools/phase06_rahti.sh routes --execute
```

Only after CSC has approved/assigned the LoadBalancer ingress IP and the owner
has separately approved exposure:

```sh
export ROAD_SENSE_APPROVED=yes
export ROAD_SENSE_PUBLIC_ENDPOINT_APPROVED=yes
export RAHTI_MQTT_LOADBALANCER_APPROVED=yes
./tools/phase06_rahti.sh mqtt-external --execute
```

Create/verify a DNS A record for the assigned public IP, include that name in
the broker certificate SAN, and configure the VPS for that hostname and port
`30883`. Verify authenticated TLS from the VPS, denied access from an
unapproved network, Service endpoints, source-IP filtering, and broker logs.
The API NetworkPolicy uses CSC's documented router namespace label
`policy-group.network.openshift.io/ingress`. Recheck it on the actual cluster.
If either allowlist fails, remove the affected external resource and use an
approved private alternative. Never disable TLS verification.

## 7. Prepare VPS Compose without public dashboard

Only after explicit VPS approval, copy the deployment files to the VPS and
put the MUHOS archives in a private readable directory; no archive enters Git.
Copy ONLY the CA **certificate** (not the CA private key).

```sh
cd infrastructure/vps
cp .env.example .env
cp dashboard.env.example dashboard.env
cp sensor-replay.env.example sensor-replay.env
chmod 600 .env dashboard.env sensor-replay.env
# .env has only Compose interpolation (2 pinned images, host paths, port).
# dashboard.env has only the HTTPS API URL. sensor-replay.env has only replay
# settings and the approved LoadBalancer DNS/port 30883/credentials. Never
# combine these files.
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
- **Processor:** preserve its state PVC across rollbacks. A compatible image
  must replay the journal before readiness; do not delete it during an active run.
- **External access:** withdraw an unapproved/insecure API Route or MQTT
  LoadBalancer Service promptly without deleting database/broker/state storage.
- **Secrets:** never print credentials, commit .env files, or paste tokens.

## 10. Work remaining before Phase 06 can be called complete

- [x] Verify Phase 02–05 local tests on the corrected branch commit.
- [ ] Inspect real VPS and Rahti project/quota/storage/permissions.
- [ ] Verify every registry image digest including PostgreSQL candidate.
- [ ] Verify Mosquitto and Postgres run under Rahti restricted SCC + PVCs.
- [ ] Verify the broker PVC write init check and persistent-session recovery on Rahti.
- [ ] Obtain CSC LoadBalancer approval and test MQTT/TLS on port 30883.
- [ ] Approve and execute registry publish, Rahti deploy and VPS deploy stages.
- [ ] Verify end-to-end remote telemetry, restart/persistence, backups/rollback.
- [ ] Record sanitized remote evidence in a Phase 06 implementation report.

Offline correction evidence is recorded in [the Phase 06 report](phase-06-report.md).
This guide is an educational deployment runbook, **not a claim that remote
infrastructure is deployed**.
