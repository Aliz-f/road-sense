#!/usr/bin/env bash
# Stage-by-stage approved OpenShift actions. NEVER runs without --execute and approval.
set -euo pipefail
stage="${1:-}"
mode="${2:-}"
case "$stage" in secrets|core|migrate|apps|routes|status) ;; *)
  echo "Usage: $0 secrets|core|migrate|apps|routes|status --execute" >&2; exit 2;;
esac
: "${RAHTI_NAMESPACE:?set explicit target Rahti project name}"
command -v oc >/dev/null || { echo "oc CLI not installed" >&2; exit 1; }
active=$(oc project -q)
if [[ "$active" != "$RAHTI_NAMESPACE" ]]; then
  echo "Refusing: active oc project '$active' differs from RAHTI_NAMESPACE '$RAHTI_NAMESPACE'" >&2
  exit 2
fi
if [[ "$mode" != "--execute" || "${ROAD_SENSE_APPROVED:-}" != yes ]]; then
  echo "PLAN ONLY: would run stage $stage in namespace $RAHTI_NAMESPACE"
  echo "Requires: ROAD_SENSE_APPROVED=yes $0 $stage --execute"
  exit 0
fi
root=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
out="${RAHTI_MANIFEST_DIR:-$root/infrastructure/rahti/generated}"
oc_ns() { oc -n "$RAHTI_NAMESPACE" "$@"; }
if [[ "$stage" == secrets ]]; then
  : "${PHASE06_SECRET_DIR:?set path to private generated materials}"
  for file in mqtt-password postgres-password password_file ca.crt server.crt server.key; do
    [[ -s "$PHASE06_SECRET_DIR/$file" ]] || { echo "missing private file: $file" >&2; exit 2; }
  done
  oc_ns create secret generic roadsense-mqtt-auth \
    --from-literal=username=roadsense-remote \
    --from-file=password="$PHASE06_SECRET_DIR/mqtt-password" \
    --from-file=password_file="$PHASE06_SECRET_DIR/password_file" \
    --dry-run=client -o yaml | oc_ns apply -f -
  oc_ns create secret generic roadsense-mqtt-tls \
    --from-file=ca.crt="$PHASE06_SECRET_DIR/ca.crt" \
    --from-file=server.crt="$PHASE06_SECRET_DIR/server.crt" \
    --from-file=server.key="$PHASE06_SECRET_DIR/server.key" \
    --dry-run=client -o yaml | oc_ns apply -f -
  oc_ns create secret generic roadsense-postgres-auth \
    --from-file=password="$PHASE06_SECRET_DIR/postgres-password" \
    --dry-run=client -o yaml | oc_ns apply -f -
  echo "Secret objects created/updated. Secret VALUES were not printed."
  exit 0
fi
if [[ "$stage" == status ]]; then
  oc_ns get deployments,services,pods,pvc,jobs
  oc_ns get routes
  exit 0
fi
[[ -s "$out/$stage.yaml" ]] || { echo "missing rendered manifest $out/$stage.yaml" >&2; exit 2; }
if [[ "$stage" == routes && ${ROAD_SENSE_PUBLIC_ENDPOINT_APPROVED:-} != yes ]]; then
  echo "Public route exposure requires separate ROAD_SENSE_PUBLIC_ENDPOINT_APPROVED=yes" >&2
  exit 2
fi
if [[ "$stage" == core ]]; then
  for s in roadsense-mqtt-auth roadsense-mqtt-tls roadsense-postgres-auth; do
    oc_ns get secret "$s" >/dev/null
  done
  oc_ns apply -f "$out/core.yaml"
  oc_ns rollout status deployment/postgres --timeout=240s
  oc_ns rollout status deployment/mqtt-broker --timeout=180s
elif [[ "$stage" == migrate ]]; then
  oc_ns rollout status deployment/postgres --timeout=120s
  oc_ns apply -f "$out/migrate.yaml"
  oc_ns wait --for=condition=complete job/roadsense-migrate-v1 --timeout=240s
elif [[ "$stage" == apps ]]; then
  oc_ns wait --for=condition=complete job/roadsense-migrate-v1 --timeout=30s
  oc_ns apply -f "$out/apps.yaml"
  oc_ns rollout status deployment/signal-processor --timeout=180s
  oc_ns rollout status deployment/road-analyzer --timeout=180s
  oc_ns rollout status deployment/api --timeout=180s
else
  echo "WARNING: exposing routes; manually verify source-IP allowlist, TLS and external access."
  oc_ns apply -f "$out/routes.yaml"
  oc_ns get routes
fi
echo "Phase 06 Rahti stage $stage: resources submitted. Verify actual service functionality."
