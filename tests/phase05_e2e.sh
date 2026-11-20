#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/infrastructure/compose/local.compose.yaml"
env_file="$repository_root/config/environments/local/.env.phase02"
temporary_dir=$(mktemp -d)

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

cleanup() {
  compose down --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$temporary_dir"
}
trap cleanup EXIT HUP INT TERM

"$repository_root/tools/prepare_phase02_local.sh"
compose down --remove-orphans >/dev/null
compose config --quiet
compose build sensor-replay signal-processor road-analyzer api dashboard \
  api-unit-tests dashboard-smoke-tests dashboard-integration-helper
compose run --rm --no-deps api-unit-tests
compose run --rm --no-deps dashboard-smoke-tests
compose up --detach --wait mqtt-broker postgres signal-processor road-analyzer api dashboard

api_id=$(compose ps --quiet api)
dashboard_id=$(compose ps --quiet dashboard)
test -n "$api_id"
test -n "$dashboard_id"
test "$(docker port "$api_id" 8000/tcp)" = "127.0.0.1:8000"
test "$(docker port "$dashboard_id" 8501/tcp)" = "127.0.0.1:8501"
for service in mqtt-broker postgres signal-processor road-analyzer; do
  test -z "$(docker port "$(compose ps --quiet "$service")")"
done

run_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
replay_log="$temporary_dir/replay.log"
compose run --rm --no-deps -T -e RUN_ID="$run_id" -e REPLAY_RATE=0 \
  -e MAX_SAMPLES=1536 -e BATCH_SIZE=64 sensor-replay >"$replay_log" 2>&1
grep -q '"event":"replay_finished"' "$replay_log"
grep -q '"samples":1536' "$replay_log"

for _ in $(seq 1 300); do
  if python3 - "$run_id" <<'PY'
import json, sys, urllib.request
try:
    with urllib.request.urlopen(f"http://127.0.0.1:8000/api/v1/runs/{sys.argv[1]}/features?limit=1", timeout=1) as response:
        raise SystemExit(0 if json.load(response).get("total") == 19 else 1)
except Exception:
    raise SystemExit(1)
PY
  then
    break
  fi
  sleep 0.1
done

python3 "$repository_root/tests/verify_phase05_api.py" \
  --base-url http://127.0.0.1:8000 --run-id "$run_id" \
  --archive "$repository_root/data/raw/archives/Bumpy Gravel - imu.tar" \
  --member imu/bosch_imu.csv --max-samples 1536
compose run --rm --no-deps -T -e EXPECTED_RUN_ID="$run_id" dashboard-integration-helper

python3 - <<'PY'
import urllib.request
for url, marker in (
    ("http://127.0.0.1:8000/health/ready", b"ready"),
    ("http://127.0.0.1:8501/_stcore/health", b"ok"),
    ("http://127.0.0.1:8501", b"Streamlit"),
):
    with urllib.request.urlopen(url, timeout=10) as response:
        body = response.read()
        assert response.status == 200 and marker.lower() in body.lower(), (url, response.status)
PY

for service in mqtt-broker postgres signal-processor road-analyzer api dashboard; do
  test "$(docker inspect --format '{{.State.Status}}' "$(compose ps --quiet "$service")")" = running
done
printf '%s\n' 'Phase 05 full local real-MUHOS pipeline, API, and dashboard smoke: PASS'
