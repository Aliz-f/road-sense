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
    for resource in deployments services routes persistentvolumeclaims secrets jobs; do
      printf '%s: ' "$resource"
      oc -n "$RAHTI_NAMESPACE" auth can-i create "$resource"
    done
    echo "Confirm storage, quota, routes/TLS, image pull access and SCC separately."
    ;;
  vps)
    uname -m
    cat /etc/os-release
    nproc
    free -h
    df -h /
    docker version
    docker compose version
    echo "Read-only VPS inspection complete."
    ;;
  *)
    echo "Usage: $0 local|rahti|vps" >&2
    exit 2
    ;;
esac
