#!/usr/bin/env bash
# Build/push versioned images only after explicit approval; defaults to plan-only.
set -euo pipefail
if [[ $# -ne 1 || ( $1 != --plan && $1 != --execute ) ]]; then
  echo "Usage: GHCR_OWNER=... $0 --plan|--execute" >&2; exit 2
fi
: "${GHCR_OWNER:?set approved GHCR namespace}"
owner="${GHCR_OWNER,,}"
[[ $owner =~ ^[a-z0-9][a-z0-9-]*$ ]] || { echo "invalid GHCR_OWNER" >&2; exit 2; }
version="${RELEASE_VERSION:-$(git rev-parse --short=12 HEAD)}"
platform="${RELEASE_PLATFORM:-linux/amd64}"
[[ $version =~ ^[a-zA-Z0-9._-]+$ ]] || { echo "invalid RELEASE_VERSION" >&2; exit 2; }
if [[ $1 == --execute && ${ROAD_SENSE_APPROVED:-} != yes ]]; then
  echo "Explicit approval required: ROAD_SENSE_APPROVED=yes" >&2; exit 2
fi
git diff --quiet && git diff --cached --quiet || { echo "commit and review local changes before publishing" >&2; exit 2; }
declare -a services=(signal-processor road-analyzer api mqtt-broker)
for service in "${services[@]}"; do
  if [[ $service == mqtt-broker ]]; then
    dockerfile=infrastructure/rahti/mosquitto/Dockerfile
  else
    dockerfile="services/$service/Dockerfile"
  fi
  image="ghcr.io/$owner/road-sense-$service:$version"
  if [[ $service == mqtt-broker ]]; then
    target_args=()
  else
    target_args=(--target runtime)
  fi
  if [[ $1 == --plan ]]; then
    printf 'PLAN: docker buildx build --platform %q' "$platform"
    printf ' %q' "${target_args[@]}"
    printf ' -f %q -t %q --push .\n' "$dockerfile" "$image"
  else
    echo "Building and pushing: $image"
    docker buildx build --platform "$platform" "${target_args[@]}" -f "$dockerfile" -t "$image" --push .
    echo "Inspect and record immutable manifest digest:"
    docker buildx imagetools inspect "$image"
  fi
done
echo "Pin image digests in infrastructure/rahti/images.env."
echo "Sensor Replay and Dashboard continue to use locally built Compose images on the laptop."
echo "PostgreSQL is a separate OpenShift-compatible upstream image; verify and pin its digest."
