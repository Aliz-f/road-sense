# Phase 06 private Rahti deployment

No Rahti resource has been deployed by repository preparation. Active templates
are deliberately limited to:

1. `core.yaml.tpl` — ConfigMaps, private PostgreSQL/Mosquitto Services,
   Deployments, PVCs and PostgreSQL NetworkPolicy.
2. `migrate.yaml.tpl` — a fresh release-bound migration Job.
3. `apps.yaml.tpl` — Signal Processor, Road Analyzer, read-only FastAPI and API
   ingress policy.
4. `mosquitto/Dockerfile` — arbitrary-UID-compatible broker image.

`routes.yaml.tpl` and `mqtt-external.yaml.tpl` document the abandoned VPS-era
public design. Current render/apply scripts cannot select them.

## Constraints

- Verify the real namespace, quota, storage class, SCC/UID/seccomp behavior,
  registry access and NetworkPolicy behavior before deployment.
- Pin every image by digest. The PostgreSQL example is a candidate until live
  arbitrary-UID startup and PVC persistence are verified.
- Keep client credentials and TLS keys in OpenShift Secrets, never Git YAML.
- Keep one processor and analyzer replica. Preserve the processor journal,
  broker data and PostgreSQL PVCs across rollouts.
- The active baseline has only ClusterIP Services. PostgreSQL remains private;
  laptop access to MQTT/API uses loopback-only authenticated `oc port-forward`.
- The Mosquitto Deployment has no LoadBalancer-specific node selector.

## Render and guarded deployment

```sh
cp infrastructure/rahti/images.env.example infrastructure/rahti/images.env
python3 tools/phase06_render_rahti.py \
  --settings infrastructure/rahti/images.env \
  --output-dir infrastructure/rahti/generated

export RAHTI_NAMESPACE=REPLACE_ACTUAL_EXISTING_PROJECT
export PHASE06_SECRET_DIR=/private/path/to/phase06-secrets
export ROAD_SENSE_APPROVED=yes
./tools/phase06_rahti.sh secrets --execute
./tools/phase06_rahti.sh core --execute
./tools/phase06_rahti.sh migrate --execute
./tools/phase06_rahti.sh apps --execute
./tools/phase06_rahti.sh status --execute
```

The commands require explicit approval and a matching active `oc` project.
Never delete PVCs for rollback. See
`../../docs/phase-06-deployment-guide.md` for prerequisites, laptop forwards,
verification and recovery.
