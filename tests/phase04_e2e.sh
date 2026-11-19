#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/infrastructure/compose/local.compose.yaml"
env_file="$repository_root/config/environments/local/.env.phase02"
event_log=$(mktemp)
duplicate_event_log=$(mktemp)
replay_log=$(mktemp)
event_subscriber_pid=

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

cleanup() {
  if test -n "$event_subscriber_pid"; then
    kill "$event_subscriber_pid" >/dev/null 2>&1 || true
    wait "$event_subscriber_pid" >/dev/null 2>&1 || true
  fi
  compose down --remove-orphans >/dev/null 2>&1 || true
  rm -f "$event_log" "$duplicate_event_log" "$replay_log"
}
trap cleanup EXIT HUP INT TERM

wait_for_log() {
  service=$1
  pattern=$2
  minimum=$3
  ready=false
  for _ in $(seq 1 200); do
    count=$(compose logs "$service" 2>/dev/null | grep -c "$pattern" || true)
    if test "$count" -ge "$minimum"; then
      ready=true
      break
    fi
    sleep 0.1
  done
  if test "$ready" != true; then
    compose logs "$service" >&2 || true
    printf 'timed out waiting for %s in %s\n' "$pattern" "$service" >&2
    exit 1
  fi
}

start_event_subscriber() {
  log_file=$1
  run_id=$2
  expected=$3
  compose run --rm --no-deps -T \
    -e EXPECTED_RUN_ID="$run_id" \
    -e EXPECTED_EVENTS="$expected" \
    -e SUBSCRIBER_TIMEOUT_SECONDS=120 \
    event-subscriber >"$log_file" 2>&1 &
  event_subscriber_pid=$!
  ready=false
  for _ in $(seq 1 150); do
    if grep -q 'event_subscriber_ready' "$log_file"; then
      ready=true
      break
    fi
    if ! kill -0 "$event_subscriber_pid" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done
  if test "$ready" != true; then
    cat "$log_file" >&2
    printf '%s\n' 'event subscriber did not become ready' >&2
    exit 1
  fi
}

wait_event_subscriber() {
  log_file=$1
  if ! wait "$event_subscriber_pid"; then
    event_subscriber_pid=
    cat "$log_file" >&2
    exit 1
  fi
  event_subscriber_pid=
  grep -q 'event_subscriber_complete' "$log_file"
}

integration_helper() {
  command=$1
  run_id=$2
  compose run --rm --no-deps -T --entrypoint python \
    analyzer-integration-helper tests/integration_helper.py "$command" "$run_id"
}

"$repository_root/tools/prepare_phase02_local.sh"
compose config --quiet
compose build sensor-replay signal-processor road-analyzer event-subscriber \
  analyzer-unit-tests analyzer-integration-helper
compose run --rm --no-deps analyzer-unit-tests
compose up --detach --wait mqtt-broker postgres signal-processor road-analyzer
wait_for_log road-analyzer '"event":"analyzer_ready"' 1

broker_id=$(compose ps --quiet mqtt-broker)
postgres_id=$(compose ps --quiet postgres)
analyzer_id=$(compose ps --quiet road-analyzer)
test -n "$broker_id"
test -n "$postgres_id"
test -n "$analyzer_id"
test -z "$(docker port "$broker_id")"
test -z "$(docker port "$postgres_id")"
test -z "$(docker port "$analyzer_id")"

compose stop --timeout 5 mqtt-broker >/dev/null
compose start mqtt-broker >/dev/null
broker_id=$(compose ps --quiet mqtt-broker)
broker_healthy=false
for _ in $(seq 1 150); do
  if test "$(docker inspect --format '{{.State.Health.Status}}' "$broker_id")" = healthy; then
    broker_healthy=true
    break
  fi
  sleep 0.2
done
if test "$broker_healthy" != true; then
  compose logs mqtt-broker >&2
  exit 1
fi
wait_for_log road-analyzer '"event":"analyzer_ready"' 2
printf '%s\n' 'Phase 04 analyzer MQTT interruption/reconnection: PASS'

run_id=44444444-4444-4444-8444-444444444444
start_event_subscriber "$event_log" "$run_id" 5
compose run --rm --no-deps -T \
  -e RUN_ID="$run_id" \
  -e REPLAY_RATE=0 \
  -e MAX_SAMPLES=1536 \
  -e BATCH_SIZE=64 \
  sensor-replay >"$replay_log" 2>&1
grep -q '"event":"replay_finished"' "$replay_log"
grep -q '"samples":1536' "$replay_log"
wait_event_subscriber "$event_log"
grep -q '"event_count":5' "$event_log"
grep -q '"window_indices":\[13,14,15,16,18\]' "$event_log"
integration_helper verify "$run_id"
printf '%s\n' 'Phase 04 real-data storage and event generation: PASS'

start_event_subscriber "$duplicate_event_log" "$run_id" 1
duplicate_before=$(compose logs road-analyzer 2>/dev/null | grep -c '"event":"feature_duplicate"' || true)
integration_helper duplicate "$run_id"
wait_event_subscriber "$duplicate_event_log"
wait_for_log road-analyzer '"event":"feature_duplicate"' "$((duplicate_before + 1))"

conflict_before=$(compose logs road-analyzer 2>/dev/null | grep -c '"event":"feature_conflict"' || true)
integration_helper conflict "$run_id"
wait_for_log road-analyzer '"event":"feature_conflict"' "$((conflict_before + 1))"
integration_helper verify "$run_id"
printf '%s\n' 'Phase 04 exact duplicate idempotency and conflicting duplicate rejection: PASS'

volume_name=roadsense-local-postgres-data
docker volume inspect "$volume_name" >/dev/null
compose down --remove-orphans >/dev/null
docker volume inspect "$volume_name" >/dev/null
compose up --detach --wait postgres
compose run --rm --no-deps analyzer-migrate
integration_helper verify "$run_id"
printf '%s\n' 'Phase 04 PostgreSQL persistence after container recreation: PASS'

cat "$event_log"
cat "$duplicate_event_log"
printf '%s\n' 'Phase 04 analyzer/storage acceptance checks: PASS'
