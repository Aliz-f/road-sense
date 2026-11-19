#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/infrastructure/compose/preflight.compose.yaml"
local_env="$repository_root/config/environments/local/.env"
local_template="$repository_root/config/environments/local/.env.example"

cleanup() {
  docker compose -f "$compose_file" down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT HUP INT TERM

printf '%s\n' 'Phase 01 local validation'
docker --version
docker compose version
printf 'context=%s\n' "$(docker context show)"
docker version --format 'server={{.Server.Version}} desktop={{.Server.Platform.Name}}'

test -f "$local_env"
dataset_root=$(sed -n 's/^ROADSENSE_DATASET_ROOT=//p' "$local_env")
test -n "$dataset_root"
test -d "$dataset_root"
test -r "$dataset_root/Bumpy Gravel - imu.tar"

for variable in MQTT_BIND_ADDRESS API_BIND_ADDRESS DASHBOARD_BIND_ADDRESS; do
  value=$(sed -n "s/^${variable}=//p" "$local_template")
  test "$value" = 127.0.0.1
done
test -z "$(sed -n -E '/^(MQTT_PASSWORD|POSTGRES_PASSWORD)=.+/p' "$local_template")"

git -C "$repository_root" check-ignore -q data/raw/archives/'Bumpy Gravel - imu.tar'
test -z "$(git -C "$repository_root" ls-files data/raw)"

docker compose -f "$compose_file" config --quiet
test "$(docker compose -f "$compose_file" config --images)" = \
  'docker.io/library/busybox:1.36.1@sha256:73aaf090f3d85aa34ee199857f03fa3a95c8ede2ffd4cc2cdb5b94e566b11662'

docker compose -f "$compose_file" up --detach --wait --wait-timeout 30
container_id=$(docker compose -f "$compose_file" ps --quiet engine-check)
test -n "$container_id"
test "$(docker inspect --format '{{.State.Health.Status}}' "$container_id")" = healthy
test -z "$(docker port "$container_id")"
test "$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' "$container_id")" = true
test "$(docker inspect --format '{{index .NetworkSettings.Networks "roadsense-phase01-preflight_preflight" | printf "%t" .}}' "$container_id")" != '<nil>'

printf '%s\n' 'Phase 01 local validation: PASS'
