#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/infrastructure/compose/local.compose.yaml"
env_file="$repository_root/config/environments/local/.env.phase02"
subscriber_log=$(mktemp)
replay_log=$(mktemp)
subscriber_pid=

if test "${PHASE02_FULL_REPLAY:-false}" = true; then
  expected_messages=972
  expected_samples=62169
  max_samples=0
else
  expected_messages=2
  expected_samples=128
  max_samples=128
fi

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

cleanup() {
  if test -n "$subscriber_pid"; then
    kill "$subscriber_pid" >/dev/null 2>&1 || true
    wait "$subscriber_pid" >/dev/null 2>&1 || true
  fi
  compose down --remove-orphans >/dev/null 2>&1 || true
  rm -f "$subscriber_log" "$replay_log"
}
trap cleanup EXIT HUP INT TERM

"$repository_root/tools/prepare_phase02_local.sh"
compose config --quiet
compose build sensor-replay mqtt-subscriber unit-tests
compose run --rm --no-deps unit-tests
compose up --detach --wait mqtt-broker

broker_id=$(compose ps --quiet mqtt-broker)
test -n "$broker_id"
test -z "$(docker port "$broker_id")"

set -a
. "$env_file"
set +a
if compose exec -T mqtt-broker mosquitto_sub \
  -h localhost -p 8883 --cafile /run/roadsense/mqtt/ca.crt \
  -u "$MQTT_USERNAME" -P invalid-password \
  -t 'roadsense/v1/imu/raw' -C 1 -W 2 >/dev/null 2>&1; then
  printf '%s\n' 'broker accepted an invalid password' >&2
  exit 1
fi
printf '%s\n' 'authenticated broker rejection check: PASS'
if compose exec -T mqtt-broker mosquitto_sub \
  -h localhost -p 8883 --cafile /run/roadsense/mqtt/ca.crt \
  -t 'roadsense/v1/imu/raw' -C 1 -W 2 >/dev/null 2>&1; then
  printf '%s\n' 'broker accepted an anonymous client' >&2
  exit 1
fi
printf '%s\n' 'anonymous broker rejection check: PASS'

compose run --rm --no-deps -T \
  -e EXPECTED_MESSAGES="$expected_messages" \
  -e EXPECTED_SAMPLES="$expected_samples" \
  -e EXPECTED_FIRST_TIMESTAMP=2026-10-19T05:51:57.052Z \
  -e SUBSCRIBER_TIMEOUT_SECONDS=60 \
  mqtt-subscriber >"$subscriber_log" 2>&1 &
subscriber_pid=$!

ready=false
for _ in $(seq 1 100); do
  if grep -q 'subscriber_ready' "$subscriber_log"; then
    ready=true
    break
  fi
  if ! kill -0 "$subscriber_pid" 2>/dev/null; then
    break
  fi
  sleep 0.1
done
if test "$ready" != true; then
  cat "$subscriber_log" >&2
  printf '%s\n' 'subscriber did not become ready' >&2
  exit 1
fi

compose run --rm --no-deps -T \
  -e REPLAY_RATE=0 \
  -e MAX_SAMPLES="$max_samples" \
  -e BATCH_SIZE=64 \
  sensor-replay | tee "$replay_log"

if ! wait "$subscriber_pid"; then
  subscriber_pid=
  cat "$subscriber_log" >&2
  exit 1
fi
subscriber_pid=
cat "$subscriber_log"

grep -q '"event":"replay_finished"' "$replay_log"
grep -q "\"messages\":$expected_messages" "$replay_log"
grep -q "\"samples\":$expected_samples" "$replay_log"
grep -q '"event": "subscriber_complete"' "$subscriber_log"
printf '%s\n' 'Phase 02 real-data MQTT end-to-end: PASS'
