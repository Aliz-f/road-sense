# Phase 06 Rahti deployment preparation

**Repository files prepared; no Rahti service has been deployed or changed.**
OpenShift templates are split into ordered, reversible stages:

1. `core.yaml.tpl`: ConfigMaps, private PostgreSQL Service/Deployment/PVC,
   broker Service/Deployment/PVC and PostgreSQL-only ingress NetworkPolicy.
2. `migrate.yaml.tpl`: one-off SQL schema migration Job.
3. `apps.yaml.tpl`: Signal Processor, Road Analyzer and read-only FastAPI.
4. `routes.yaml.tpl`: OPTIONAL external MQTT TLS passthrough and HTTPS API
   Routes with VPS egress allowlist. **Never apply without explicit approval.**
5. `mosquitto/Dockerfile`: broker image adapted for OpenShift's assigned UID.

## Deployment constraints
- Verify Rahti project, quota, storage class, allowed SCC/UID, image pull
  access and real TLS passthrough routes BEFORE running any apply command.
- The candidate `quay.io/sclorg/postgresql-16-c9s` is intended for arbitrary
  OpenShift UIDs, but image, digest and startup behavior MUST be validated
  on the real cluster. Never substitute the local Docker Hub Postgres image blindly.
- All application images must use immutable registry digests; templates cannot
  accept tags or `:latest`.
- Client usernames/passwords and TLS keys live in Kubernetes Secrets, generated
  from locally protected files, not Git YAML or a ConfigMap.
- Only one MQTT processor/analyzer replica for this MVP. Both use stable client IDs.
- No public DB Route/port. No API/MQTT external routes in the core stage.
- The API is read-only at the SQL transaction level but does not yet have a
  separate least-privilege DB role. Remote API route requires a VERIFIED source
  allowlist and guarded access before exposing it.
- Route TCP TLS passthrough is a DEPLOYMENT GATE, not assumed to work. Use
  broker hostname with SNI and port 443 if the cluster supports passthrough.

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

# External route stage only with a separate approval after private validation.
# See docs guide for route rendering and security checks.
```

## Rollback
Use `oc rollout history deployment/<name>` and `oc rollout undo
deployment/<name>` selectively. Record images before changing them.
Do NOT delete PVCs, Secrets, project, namespace or data as a rollback step.
For migration errors, preserve the database and inspect Job logs before retry.
Back up persistent data before first production deployment or disruptive change.

See `../../docs/phase-06-deployment-guide.md` for commands and explanations.
