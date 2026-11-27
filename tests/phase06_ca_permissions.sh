#!/usr/bin/env bash
# Runtime regression check for locally generated Phase 06 secret permissions.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# Keep the bind source under the repository so Docker Desktop installations
# that share only the project directory can run this check.
mkdir -p "$repo_root/infrastructure/rahti/generated"
test_root=$(mktemp -d "$repo_root/infrastructure/rahti/generated/.phase06-ca-test.XXXXXX")
secret_dir="$test_root/secrets"
image="roadsense/sensor-replay:phase06-permissions-test"
trap 'rm -rf "$test_root"' EXIT

"$repo_root/tools/phase06_prepare_secrets.sh" --local-only localhost "$secret_dir" >/dev/null

assert_mode() {
  local expected=$1
  local path=$2
  local actual
  actual=$(stat -c '%a' "$path")
  if [[ $actual != "$expected" ]]; then
    printf 'unexpected permissions on %s: expected %s, got %s\n' "$(basename "$path")" "$expected" "$actual" >&2
    exit 1
  fi
}

assert_mode 700 "$secret_dir"
for name in ca.key server.key mqtt-password postgres-password password_file server.csr server.ext ca.srl; do
  assert_mode 600 "$secret_dir/$name"
done
assert_mode 644 "$secret_dir/ca.crt"
assert_mode 644 "$secret_dir/server.crt"

docker build --quiet --target runtime \
  --file "$repo_root/services/sensor-replay/Dockerfile" \
  --tag "$image" "$repo_root" >/dev/null
docker run --rm --network none \
  --volume "$secret_dir/ca.crt:/run/roadsense/mqtt/ca.crt:ro" \
  --entrypoint python "$image" -c \
  'import os, pathlib; assert os.getuid() == 10001; assert b"BEGIN CERTIFICATE" in pathlib.Path("/run/roadsense/mqtt/ca.crt").read_bytes()'

echo "Phase 06 CA permission check passed for Sensor Replay UID 10001."
