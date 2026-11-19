#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/infrastructure/compose/local.compose.yaml"
env_file="$repository_root/config/environments/local/.env.phase02"
unpaced_log=$(mktemp)
paced_log=$(mktemp)
full_log=$(mktemp)
partial_log=$(mktemp)
replay_log=$(mktemp)
subscriber_pid=

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

cleanup() {
  if test -n "$subscriber_pid"; then
    kill "$subscriber_pid" >/dev/null 2>&1 || true
    wait "$subscriber_pid" >/dev/null 2>&1 || true
  fi
  compose down --remove-orphans >/dev/null 2>&1 || true
  rm -f "$unpaced_log" "$paced_log" "$full_log" "$partial_log" "$replay_log"
}
trap cleanup EXIT HUP INT TERM

wait_for_subscriber() {
  log_file=$1
  ready=false
  for _ in $(seq 1 150); do
    if grep -q 'feature_subscriber_ready' "$log_file"; then
      ready=true
      break
    fi
    if ! kill -0 "$subscriber_pid" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done
  if test "$ready" != true; then
    cat "$log_file" >&2
    printf '%s\n' 'feature subscriber did not become ready' >&2
    exit 1
  fi
}

run_replay() {
  replay_rate=$1
  run_id=$2
  feature_log=$3
  max_samples=$4
  expected_features=$5
  expected_samples=$6
  include_features=$7
  compose run --rm --no-deps -T \
    -e EXPECTED_RUN_ID="$run_id" \
    -e EXPECTED_FEATURES="$expected_features" \
    -e SUBSCRIBER_INCLUDE_FEATURES="$include_features" \
    -e SUBSCRIBER_TIMEOUT_SECONDS=120 \
    feature-subscriber >"$feature_log" 2>&1 &
  subscriber_pid=$!
  wait_for_subscriber "$feature_log"

  compose run --rm --no-deps -T \
    -e RUN_ID="$run_id" \
    -e REPLAY_RATE="$replay_rate" \
    -e MAX_SAMPLES="$max_samples" \
    -e BATCH_SIZE=64 \
    sensor-replay >"$replay_log" 2>&1
  grep -q '"event":"replay_finished"' "$replay_log"
  grep -q "\"samples\":$expected_samples" "$replay_log"

  if ! wait "$subscriber_pid"; then
    subscriber_pid=
    cat "$feature_log" >&2
    cat "$replay_log" >&2
    exit 1
  fi
  subscriber_pid=
  grep -q 'feature_subscriber_complete' "$feature_log"
}

"$repository_root/tools/prepare_phase02_local.sh"
compose config --quiet
compose build sensor-replay signal-processor feature-subscriber processor-unit-tests
compose run --rm --no-deps processor-unit-tests
compose up --detach --wait mqtt-broker signal-processor

processor_ready=false
for _ in $(seq 1 150); do
  if compose logs signal-processor 2>/dev/null | grep -q '"event":"processor_ready"'; then
    processor_ready=true
    break
  fi
  sleep 0.1
done
if test "$processor_ready" != true; then
  compose logs signal-processor >&2
  printf '%s\n' 'signal processor did not become ready' >&2
  exit 1
fi

broker_id=$(compose ps --quiet mqtt-broker)
processor_id=$(compose ps --quiet signal-processor)
test -n "$broker_id"
test -n "$processor_id"
test -z "$(docker port "$broker_id")"
test -z "$(docker port "$processor_id")"

run_replay 0 11111111-1111-4111-8111-111111111111 "$unpaced_log" 256 3 256 true
run_replay 10 22222222-2222-4222-8222-222222222222 "$paced_log" 256 3 256 true

set -a
. "$env_file"
set +a
python3 "$repository_root/tests/verify_phase03_features.py" \
  --unpaced-log "$unpaced_log" \
  --paced-log "$paced_log" \
  --archive "$ROADSENSE_DATASET_ROOT/$ROADSENSE_MVP_ARCHIVE" \
  --member "$ROADSENSE_MVP_MEMBER" \
  --max-samples 256

cat "$unpaced_log"
cat "$paced_log"
printf '%s\n' 'Phase 03 real-data feature pipeline and replay-rate invariance: PASS'

if test "${PHASE03_FULL_REPLAY:-false}" = true; then
  full_run_id=33333333-3333-4333-8333-333333333333
  run_replay 0 "$full_run_id" "$full_log" 0 746 62169 false
  grep -q '"feature_count":746' "$full_log"
  grep -q '"first_window_index":0' "$full_log"
  grep -q '"last_window_index":745' "$full_log"
  cat "$full_log"
  printf '%s\n' 'Phase 03 full-recording feature delivery: PASS'

  compose run --rm --no-deps -T \
    -e EXPECTED_RUN_ID="$full_run_id" \
    -e EXPECTED_FEATURES=1 \
    -e EXPECTED_FIRST_WINDOW_INDEX=746 \
    -e SUBSCRIBER_TIMEOUT_SECONDS=60 \
    feature-subscriber >"$partial_log" 2>&1 &
  subscriber_pid=$!
  wait_for_subscriber "$partial_log"
  compose stop --timeout 15 signal-processor >/dev/null
  if ! wait "$subscriber_pid"; then
    subscriber_pid=
    cat "$partial_log" >&2
    compose logs signal-processor >&2
    exit 1
  fi
  subscriber_pid=
  grep -q '"feature_count":1' "$partial_log"
  grep -q '"first_window_index":746' "$partial_log"
  grep -q '"last_window_index":746' "$partial_log"
  grep -q '"incomplete_window"' "$partial_log"
  cat "$partial_log"
  printf '%s\n' 'Phase 03 graceful final-window flush: PASS'
fi
