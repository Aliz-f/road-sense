#!/usr/bin/env bash
# Read-only verification helpers; no deployment or changes.
set -euo pipefail
case "${1:-}" in
  rahti)
    : "${RAHTI_NAMESPACE:?set intended namespace}"
    oc -n "$RAHTI_NAMESPACE" get pods,deployments,services,pvc,jobs,networkpolicies
    for deployment in postgres mqtt-broker signal-processor road-analyzer api; do
      oc -n "$RAHTI_NAMESPACE" rollout status "deployment/$deployment" --timeout=10s
    done
    echo "Kubernetes workload health checked; this does not replace real remote E2E validation."
    ;;
  *)
    echo "Usage: $0 rahti" >&2; exit 2;;
esac
