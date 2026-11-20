#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/infrastructure/compose/local.compose.yaml"
env_file="$repository_root/config/environments/local/.env.phase02"
temporary_dir=$(mktemp -d)
postgres_previous="$repository_root/config/environments/local/runtime/postgres/password.previous"

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

cleanup() {
  if test -f "$postgres_previous"; then
    compose up --detach --wait postgres >/dev/null 2>&1 || true
    compose run --rm --no-deps -T api-credential-rotation-helper recover \
      >/dev/null 2>&1 || true
  fi
  compose down --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$temporary_dir"
}
trap cleanup EXIT HUP INT TERM

"$repository_root/tools/prepare_phase02_local.sh"
compose down --remove-orphans >/dev/null
compose config --quiet
compose build sensor-replay signal-processor road-analyzer api dashboard \
  api-unit-tests api-credential-rotation-helper dashboard-smoke-tests \
  dashboard-integration-helper
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

compose run --rm --no-deps -T api-credential-rotation-helper stage
compose restart api >/dev/null
compose up --detach --wait api >/dev/null
python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=10) as response:
    assert json.load(response) == {"status": "ready"}
PY
compose run --rm --no-deps -T api-credential-rotation-helper recover
test ! -e "$postgres_previous"
compose restart api >/dev/null
compose up --detach --wait api >/dev/null
printf '%s\n' 'Phase 05 FastAPI password fallback during interrupted rotation: PASS'

run_replay() {
  run_id=$1
  archive=$2
  member=$3
  archive_hash=$4
  session_id=$5
  log_file=$6
  compose run --rm --no-deps -T \
    -e RUN_ID="$run_id" -e REPLAY_RATE=0 -e MAX_SAMPLES=1536 -e BATCH_SIZE=64 \
    -e ROADSENSE_MVP_ARCHIVE="$archive" -e ROADSENSE_MVP_MEMBER="$member" \
    -e SOURCE_ARCHIVE_SHA256="$archive_hash" -e SESSION_ID="$session_id" \
    sensor-replay >"$log_file" 2>&1
  grep -q '"event":"replay_finished"' "$log_file"
  grep -q '"samples":1536' "$log_file"
}

wait_for_features() {
  run_id=$1
  expected=$2
  for _ in $(seq 1 300); do
    if python3 - "$run_id" "$expected" <<'PY'
import json, sys, urllib.request
try:
    with urllib.request.urlopen(f"http://127.0.0.1:8000/api/v1/runs/{sys.argv[1]}/features?limit=1", timeout=1) as response:
        raise SystemExit(0 if json.load(response).get("total") == int(sys.argv[2]) else 1)
except Exception:
    raise SystemExit(1)
PY
    then
      return
    fi
    sleep 0.1
  done
  printf 'timed out waiting for API features for run %s\n' "$run_id" >&2
  exit 1
}

bumpy_run_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
paved_run_id=$(python3 -c 'import uuid; print(uuid.uuid4())')
run_replay "$bumpy_run_id" "Bumpy Gravel - imu.tar" "imu/bosch_imu.csv" \
  "91d37ad4de7106d5038ed7bffe1e373db65e0f4771865da8975a216e76ed34f3" \
  "bumpy-gravel-20261019" "$temporary_dir/bumpy-replay.log"
run_replay "$paved_run_id" "Paved Road 60kmh - imu.tar" "imu/bosch_imu.csv" \
  "cf3d0002573f1ecaa021034a3a20dee6cbb21a47989026d8b4ed0c8a81b7c6a4" \
  "paved-road-60kmh-20261007" "$temporary_dir/paved-replay.log"
wait_for_features "$bumpy_run_id" 19
wait_for_features "$paved_run_id" 19

python3 "$repository_root/tests/verify_phase05_api.py" \
  --base-url http://127.0.0.1:8000 --run-id "$bumpy_run_id" \
  --session-id bumpy-gravel-20261019 \
  --archive "$repository_root/data/raw/archives/Bumpy Gravel - imu.tar" \
  --member imu/bosch_imu.csv --max-samples 1536
python3 "$repository_root/tests/verify_phase05_api.py" \
  --base-url http://127.0.0.1:8000 --run-id "$paved_run_id" \
  --session-id paved-road-60kmh-20261007 \
  --archive "$repository_root/data/raw/archives/Paved Road 60kmh - imu.tar" \
  --member imu/bosch_imu.csv --max-samples 1536

paved_event_count=$(python3 - "$paved_run_id" <<'PY'
import json, sys, urllib.request
with urllib.request.urlopen(f"http://127.0.0.1:8000/api/v1/runs/{sys.argv[1]}/events?limit=1", timeout=10) as response:
    print(json.load(response)["total"])
PY
)
compose run --rm --no-deps -T -e EXPECTED_RUN_ID="$bumpy_run_id" \
  -e EXPECTED_FEATURES=19 -e EXPECTED_EVENTS=5 dashboard-integration-helper
compose run --rm --no-deps -T -e EXPECTED_RUN_ID="$paved_run_id" \
  -e EXPECTED_FEATURES=19 -e EXPECTED_EVENTS="$paved_event_count" \
  dashboard-integration-helper

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

compose stop --timeout 5 api >/dev/null
failure_log="$temporary_dir/dashboard-api-failure.log"
if compose run --rm --no-deps -T -e EXPECTED_RUN_ID="$bumpy_run_id" \
  -e EXPECTED_FEATURES=19 -e EXPECTED_EVENTS=5 \
  dashboard-integration-helper >"$failure_log" 2>&1; then
  printf '%s\n' 'dashboard client unexpectedly succeeded while API was stopped' >&2
  exit 1
fi
grep -Eq 'ConnectionError|Failed to establish a new connection' "$failure_log"
python3 - <<'PY'
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:8501/_stcore/health", timeout=10) as response:
    assert response.status == 200 and b"ok" in response.read().lower()
PY
compose start api >/dev/null
compose up --detach --wait api >/dev/null
printf '%s\n' 'Phase 05 dashboard/API service failure and recovery handling: PASS'

for service in mqtt-broker postgres signal-processor road-analyzer api dashboard; do
  test "$(docker inspect --format '{{.State.Status}}' "$(compose ps --quiet "$service")")" = running
done
printf '%s\n' 'Phase 05 full local real-MUHOS pipeline, API, and dashboard smoke: PASS'
