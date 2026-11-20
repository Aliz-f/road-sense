# Phase 06 Rahti deployment preparation

**Repository files prepared; no Rahti service has been deployed or changed.**
OpenShift templates are split into ordered, reversible stages:

1. `core.yaml.tpl`: ConfigMaps, private PostgreSQL Service/Deployment/PVC,
   broker Service/Deployment/PVC and PostgreSQL-only ingress NetworkPolicy.
2. `migrate.yaml.tpl`: fresh release-bound SQL migration Job per execution;
   database advisory locking and checksums make repeats safe.
3. `apps.yaml.tpl`: Signal Processor, Road Analyzer and read-only FastAPI.
4. `routes.yaml.tpl`: OPTIONAL HTTPS API Route with VPS egress allowlist.
5. `mqtt-external.yaml.tpl`: OPTIONAL raw-TCP MQTT LoadBalancer Service and
   NetworkPolicy. CSC Service Desk approval for a project ingress IP is required.
6. `mosquitto/Dockerfile`: broker image adapted for OpenShift's assigned UID.

## Deployment constraints
- Verify Rahti project, quota, storage class, allowed SCC/UID, image pull
  access, and an approved LoadBalancer ingress IP BEFORE external MQTT.
- Current CSC policy requires the `rahti-custom-seccomp.json` Localhost profile
  (or an unset field for SCC defaulting); these templates request it explicitly.
- The candidate `quay.io/sclorg/postgresql-16-c9s` is intended for arbitrary
  OpenShift UIDs, but image, digest and startup behavior MUST be validated
  on the real cluster. Never substitute the local Docker Hub Postgres image blindly.
- All application images must use immutable registry digests; templates cannot
  accept tags or `:latest`.
- Client usernames/passwords and TLS keys live in Kubernetes Secrets, generated
  from locally protected files, not Git YAML or a ConfigMap.
- Only one MQTT processor/analyzer replica for this MVP. Both use stable client IDs.
- The processor journals input on its own RWO PVC before MQTT acknowledgement;
  a restart replays active runs before readiness and completed journals are pruned.
- Mosquitto startup is gated by an arbitrary-UID PVC write test; live Rahti
  restart/persistence behavior remains a required remote check.
- No public DB Route/port. No external API/MQTT resource in the core stage.
- The API is read-only at the SQL transaction level but does not yet have a
  separate least-privilege DB role. Remote API route requires a VERIFIED source
  allowlist and guarded access before exposing it.
- CSC documents Routes as HTTP(S)-only. Raw MQTT/TLS uses only a separately
  approved LoadBalancer Service on port 30883; never create an MQTT Route.

## Example execution (ONLY after owner approves the remote stage)
```sh
export RAHTI_NAMESPACE=REPLACE_ACTUAL_EXISTING_PROJECT
./tools/phase06_preflight.sh rahti

cp infrastructure/rahti/images.env.example infrastructure/rahti/images.env
# Fill in all five image digests, never tokens.
python3 tools/phase06_render_rahti.py \
  --settings infrastructure/rahti/images.env \
  --output-dir infrastructure/rahti/generated

# Put protected credentials and CA certs outside the repository if possible.
# See docs/phase-06-deployment-guide.md for generation and explicit approvals.
export PHASE06_SECRET_DIR=/private/path/to/phase06-secrets
export ROAD_SENSE_APPROVED=yes
./tools/phase06_rahti.sh secrets --execute
./tools/phase06_rahti.sh core --execute
./tools/phase06_rahti.sh migrate --execute
./tools/phase06_rahti.sh apps --execute
./tools/phase06_rahti.sh status --execute

# Add API_PUBLIC_HOST and VPS_EGRESS_CIDR, then use --include-external only
# after reviewing the API Route and CSC-approved MQTT LoadBalancer plan.
```

## Rollback
Use `oc rollout history deployment/<name>` and `oc rollout undo
deployment/<name>` selectively. Record images before changing them.
Do NOT delete PVCs, Secrets, project, namespace or data as a rollback step.
For migration errors, preserve the database and inspect Job logs before retry.
Back up persistent data before first production deployment or disruptive change.

See `../../docs/phase-06-deployment-guide.md` for commands and explanations.
