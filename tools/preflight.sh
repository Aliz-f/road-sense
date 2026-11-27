#!/usr/bin/env bash
# Read-only pre-deployment checks. Never installs or changes remote services.
set -euo pipefail
case "${1:-}" in
  local)
    command -v docker >/dev/null
    docker compose version
    docker buildx version
    git diff --check
    echo "Local toolchain inspected. No deployment performed."
    ;;
  rahti)
    command -v oc >/dev/null
    : "${RAHTI_NAMESPACE:?set the intended existing Rahti namespace}"
    echo "Current project: $(oc project -q)"
    oc -n "$RAHTI_NAMESPACE" get resourcequota
    oc -n "$RAHTI_NAMESPACE" get pvc
    oc get storageclass
    for resource in deployments services persistentvolumeclaims secrets jobs pods/portforward; do
      if permission=$(oc -n "$RAHTI_NAMESPACE" auth can-i create "$resource") && [[ $permission == yes ]]; then
        printf '%s: yes\n' "$resource"
      else
        printf '%s: denied (required)\n' "$resource" >&2
        exit 1
      fi
    done
    echo "Confirm storage, quota, image pull access, SCC and actual private port-forward connectivity separately."
    ;;
  *)
    echo "Usage: $0 local|rahti" >&2
    exit 2
    ;;
esac
