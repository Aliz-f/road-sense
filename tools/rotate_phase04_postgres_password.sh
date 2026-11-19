#!/bin/sh
set -eu

if test "${1:-}" != --apply || test "$#" -ne 1; then
  printf 'usage: %s --apply\n' "$0" >&2
  printf '%s\n' 'This explicitly rotates the local Phase 04 PostgreSQL role password.' >&2
  exit 2
fi

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/infrastructure/compose/local.compose.yaml"
env_file="$repository_root/config/environments/local/.env.phase02"

test -f "$env_file" || {
  printf '%s\n' 'missing Phase 02/04 local environment; run tools/prepare_phase02_local.sh' >&2
  exit 1
}

docker compose --env-file "$env_file" -f "$compose_file" up --detach --wait postgres
docker compose --env-file "$env_file" -f "$compose_file" \
  run --rm --no-deps postgres-password-rotate --apply
printf '%s\n' 'Phase 04 local PostgreSQL password rotation: complete'
