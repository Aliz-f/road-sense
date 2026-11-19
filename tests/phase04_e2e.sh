#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/infrastructure/compose/local.compose.yaml"
env_file="$repository_root/config/environments/local/.env.phase02"
temporary_dir=$(mktemp -d)
event_subscriber_pid=
replay_pid=
analyzer_paused=false

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

new_run_id() {
  python3 -c 'import uuid; print(uuid.uuid4())'
}

cleanup() {
  if test "$analyzer_paused" = true; then
    analyzer_id=$(compose ps --quiet road-analyzer 2>/dev/null || true)
    test -z "$analyzer_id" || docker unpause "$analyzer_id" >/dev/null 2>&1 || true
  fi
  for process_id in "$event_subscriber_pid" "$replay_pid"; do
    if test -n "$process_id"; then
      kill "$process_id" >/dev/null 2>&1 || true
      wait "$process_id" >/dev/null 2>&1 || true
    fi
  done
  compose down --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$temporary_dir"
}
trap cleanup EXIT HUP INT TERM

wait_for_log() {
  service=$1
  pattern=$2
  minimum=$3
  for _ in $(seq 1 300); do
    count=$(compose logs "$service" 2>/dev/null | grep -c "$pattern" || true)
    if test "$count" -ge "$minimum"; then
      return
    fi
    sleep 0.1
  done
  compose logs "$service" >&2 || true
  printf 'timed out waiting for %s in %s\n' "$pattern" "$service" >&2
  exit 1
}

start_event_subscriber() {
  log_file=$1
  run_id=$2
  expected=$3
  compose run --rm --no-deps -T \
    -e EXPECTED_RUN_ID="$run_id" -e EXPECTED_EVENTS="$expected" \
    -e SUBSCRIBER_TIMEOUT_SECONDS=120 event-subscriber >"$log_file" 2>&1 &
  event_subscriber_pid=$!
  for _ in $(seq 1 200); do
    if grep -q 'event_subscriber_ready' "$log_file"; then
      return
    fi
    if ! kill -0 "$event_subscriber_pid" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done
  cat "$log_file" >&2
  printf '%s\n' 'event subscriber did not become ready' >&2
  exit 1
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

wait_healthy() {
  service=$1
  container_id=$(compose ps --quiet "$service")
  for _ in $(seq 1 300); do
    if test "$(docker inspect --format '{{.State.Health.Status}}' "$container_id")" = healthy; then
      return
    fi
    sleep 0.1
  done
  compose logs "$service" >&2 || true
  printf 'service did not become healthy: %s\n' "$service" >&2
  exit 1
}

"$repository_root/tools/prepare_phase02_local.sh"
password_before=$(sha256sum "$repository_root/config/environments/local/runtime/postgres/password" | cut -d ' ' -f 1)
"$repository_root/tools/prepare_phase02_local.sh" --force
password_after_force=$(sha256sum "$repository_root/config/environments/local/runtime/postgres/password" | cut -d ' ' -f 1)
test "$password_before" = "$password_after_force"
! grep -q '^POSTGRES_PASSWORD=' "$env_file"
compose down --remove-orphans >/dev/null
printf '%s\n' 'Phase 04 forced preparation preserves the existing PostgreSQL credential: PASS'

compose config --quiet
compose build sensor-replay signal-processor road-analyzer event-subscriber \
  analyzer-unit-tests analyzer-integration-helper
compose run --rm --no-deps analyzer-unit-tests
compose up --detach --wait mqtt-broker postgres signal-processor road-analyzer
wait_for_log road-analyzer '"event":"analyzer_ready"' 1

for service in mqtt-broker postgres road-analyzer; do
  container_id=$(compose ps --quiet "$service")
  test -n "$container_id"
  test -z "$(docker port "$container_id")"
done
compose exec -T mqtt-broker test -s /mosquitto/data/mosquitto.db

core_run_id=$(new_run_id)
core_event_log="$temporary_dir/core-events.log"
core_replay_log="$temporary_dir/core-replay.log"
start_event_subscriber "$core_event_log" "$core_run_id" 5
compose run --rm --no-deps -T -e RUN_ID="$core_run_id" -e REPLAY_RATE=0 \
  -e MAX_SAMPLES=1536 -e BATCH_SIZE=64 sensor-replay >"$core_replay_log" 2>&1
grep -q '"event":"replay_finished"' "$core_replay_log"
grep -q '"samples":1536' "$core_replay_log"
wait_event_subscriber "$core_event_log"
grep -q '"event_count":5' "$core_event_log"
grep -q '"window_indices":\[13,14,15,16,18\]' "$core_event_log"
integration_helper verify "$core_run_id"
printf '%s\n' 'Phase 04 real MUHOS storage, outbox publication, and event generation: PASS'

published_before=$(compose logs road-analyzer 2>/dev/null | grep -c '"event":"event_published"' || true)
duplicate_before=$(compose logs road-analyzer 2>/dev/null | grep -c '"event":"feature_duplicate"' || true)
integration_helper duplicate "$core_run_id"
wait_for_log road-analyzer '"event":"feature_duplicate"' "$((duplicate_before + 1))"
published_after=$(compose logs road-analyzer 2>/dev/null | grep -c '"event":"event_published"' || true)
test "$published_before" = "$published_after"
conflict_before=$(compose logs road-analyzer 2>/dev/null | grep -c '"event":"feature_conflict"' || true)
integration_helper conflict "$core_run_id"
wait_for_log road-analyzer '"event":"feature_conflict"' "$((conflict_before + 1))"
integration_helper verify "$core_run_id"
printf '%s\n' 'Phase 04 duplicate redelivery is idempotent and conflicting reuse is rejected: PASS'

rule_log="$temporary_dir/rule-conflict.log"
if compose run --rm --no-deps -T \
  -e ANALYZER_VIBRATION_RMS_THRESHOLD_MG=101 \
  -e ANALYZER_RULE_VERSION=roadsense-high-vibration-rms-v1-t100 \
  road-analyzer >"$rule_log" 2>&1; then
  cat "$rule_log" >&2
  printf '%s\n' 'incompatible threshold silently reused an existing rule version' >&2
  exit 1
fi
grep -q 'rule_version is already bound to incompatible' "$rule_log"
printf '%s\n' 'Phase 04 rule versions cannot silently change threshold semantics: PASS'

database_run_id=$(new_run_id)
database_event_log="$temporary_dir/database-events.log"
start_event_subscriber "$database_event_log" "$database_run_id" 1
compose stop --timeout 5 postgres >/dev/null
integration_helper publish-reference "$database_run_id"
sleep 1
test -n "$(compose ps --status running --quiet road-analyzer)"
compose up --detach --wait postgres >/dev/null
wait_event_subscriber "$database_event_log"
integration_helper verify-single "$database_run_id"
printf '%s\n' 'Phase 04 analyzer recovers from a temporary PostgreSQL outage: PASS'

process_run_id=$(new_run_id)
process_event_log="$temporary_dir/process-events.log"
compose stop --timeout 5 road-analyzer >/dev/null
start_event_subscriber "$process_event_log" "$process_run_id" 1
integration_helper publish-reference "$process_run_id"
compose start road-analyzer >/dev/null
wait_healthy road-analyzer
wait_event_subscriber "$process_event_log"
integration_helper verify-single "$process_run_id"
printf '%s\n' 'Phase 04 persistent MQTT session recovers feature delivery after analyzer restart: PASS'

outbox_run_id=$(new_run_id)
outbox_event_log="$temporary_dir/outbox-events.log"
compose stop --timeout 5 road-analyzer >/dev/null
integration_helper store-direct "$outbox_run_id"
integration_helper verify-single-pending "$outbox_run_id"
start_event_subscriber "$outbox_event_log" "$outbox_run_id" 1
compose start road-analyzer >/dev/null
wait_healthy road-analyzer
wait_event_subscriber "$outbox_event_log"
integration_helper verify-single "$outbox_run_id"
printf '%s\n' 'Phase 04 transactional outbox publishes committed events after process restart without feature redelivery: PASS'

broker_run_id=$(new_run_id)
broker_event_log="$temporary_dir/broker-events.log"
broker_replay_log="$temporary_dir/broker-replay.log"
start_event_subscriber "$broker_event_log" "$broker_run_id" 5
analyzer_id=$(compose ps --quiet road-analyzer)
docker pause "$analyzer_id" >/dev/null
analyzer_paused=true
compose run --rm --no-deps -T -e RUN_ID="$broker_run_id" -e REPLAY_RATE=2 \
  -e MAX_SAMPLES=1536 -e BATCH_SIZE=64 -e MQTT_CONNECT_RETRIES=30 \
  -e MQTT_CONNECT_TIMEOUT_SECONDS=2 sensor-replay >"$broker_replay_log" 2>&1 &
replay_pid=$!
for _ in $(seq 1 300); do
  feature_count=$(compose logs signal-processor 2>/dev/null | grep "\"run_id\":\"$broker_run_id\"" | grep -c '"event":"feature_published"' || true)
  if test "$feature_count" -ge 2; then
    break
  fi
  sleep 0.1
done
test "$feature_count" -ge 2
sleep 2
compose kill -s KILL mqtt-broker >/dev/null
compose start mqtt-broker >/dev/null
wait_healthy mqtt-broker
docker unpause "$analyzer_id" >/dev/null
analyzer_paused=false
if ! wait "$replay_pid"; then
  replay_pid=
  cat "$broker_replay_log" >&2
  exit 1
fi
replay_pid=
wait_event_subscriber "$broker_event_log"
grep -q '"event":"replay_finished"' "$broker_replay_log"
integration_helper verify "$broker_run_id"
compose exec -T mqtt-broker test -s /mosquitto/data/mosquitto.db
printf '%s\n' 'Phase 04 persistent broker/session recovers queued features across a broker SIGKILL during active delivery: PASS'

rotation_run_id=$(new_run_id)
rotation_event_log="$temporary_dir/rotation-events.log"
rotation_password_before=$(sha256sum "$repository_root/config/environments/local/runtime/postgres/password" | cut -d ' ' -f 1)
"$repository_root/tools/rotate_phase04_postgres_password.sh" --apply
rotation_password_after=$(sha256sum "$repository_root/config/environments/local/runtime/postgres/password" | cut -d ' ' -f 1)
test "$rotation_password_before" != "$rotation_password_after"
test ! -e "$repository_root/config/environments/local/runtime/postgres/password.previous"
compose stop --timeout 5 postgres >/dev/null
start_event_subscriber "$rotation_event_log" "$rotation_run_id" 1
integration_helper publish-reference "$rotation_run_id"
compose up --detach --wait postgres >/dev/null
wait_event_subscriber "$rotation_event_log"
integration_helper verify-single "$rotation_run_id"
password_after_rotation=$rotation_password_after
"$repository_root/tools/prepare_phase02_local.sh" --force
test "$password_after_rotation" = "$(sha256sum "$repository_root/config/environments/local/runtime/postgres/password" | cut -d ' ' -f 1)"
printf '%s\n' 'Phase 04 explicit password rotation and post-restart analyzer recovery: PASS'

compose down --remove-orphans >/dev/null
docker volume inspect roadsense-local-postgres-data >/dev/null
docker volume inspect roadsense-local-mqtt-data >/dev/null
compose up --detach --wait postgres >/dev/null
compose run --rm --no-deps analyzer-migrate >/dev/null
integration_helper verify "$core_run_id"
integration_helper verify "$broker_run_id"
printf '%s\n' 'Phase 04 migrations and data persist across container recreation and repeated existing-volume startup: PASS'

cat "$core_event_log"
cat "$broker_event_log"
printf 'Phase 04 analyzer/storage reliability acceptance checks: PASS (core_run_id=%s broker_run_id=%s)\n' \
  "$core_run_id" "$broker_run_id"
