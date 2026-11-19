#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_file="$repository_root/infrastructure/compose/local.compose.yaml"
env_file="$repository_root/config/environments/local/.env.phase02"
subscriber_log=$(mktemp)
publisher_log=$(mktemp)
subscriber_pid=
publisher_name=roadsense-phase02-reconnect-publisher
publisher_id=

compose() {
  docker compose --env-file "$env_file" -f "$compose_file" "$@"
}

cleanup() {
  if test -n "$publisher_id"; then
    docker unpause "$publisher_id" >/dev/null 2>&1 || true
    docker rm -f "$publisher_id" >/dev/null 2>&1 || true
  fi
  if test -n "$subscriber_pid"; then
    kill "$subscriber_pid" >/dev/null 2>&1 || true
    wait "$subscriber_pid" >/dev/null 2>&1 || true
  fi
  compose down --remove-orphans >/dev/null 2>&1 || true
  rm -f "$subscriber_log" "$publisher_log"
}
trap cleanup EXIT HUP INT TERM

"$repository_root/tools/prepare_phase02_local.sh"
compose config --quiet
compose build sensor-replay mqtt-subscriber
compose up --detach --wait mqtt-broker

compose run --rm --no-deps -T \
  -e EXPECTED_MESSAGES=64 \
  -e EXPECTED_SAMPLES=1024 \
  -e EXPECTED_FIRST_TIMESTAMP=2026-10-19T05:51:57.052Z \
  -e SUBSCRIBER_TIMEOUT_SECONDS=90 \
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

publisher_id=$(compose run --detach --no-deps --name "$publisher_name" \
  -e REPLAY_RATE=2 \
  -e MAX_SAMPLES=1024 \
  -e BATCH_SIZE=16 \
  -e MQTT_CONNECT_RETRIES=20 \
  -e MQTT_CONNECT_TIMEOUT_SECONDS=2 \
  sensor-replay)

published_before_interrupt=false
for _ in $(seq 1 100); do
  docker logs "$publisher_id" >"$publisher_log" 2>&1 || true
  if grep -q '"sequence_id":3' "$publisher_log"; then
    published_before_interrupt=true
    break
  fi
  sleep 0.1
done
if test "$published_before_interrupt" != true; then
  cat "$publisher_log" >&2
  printf '%s\n' 'publisher did not send initial batches before interruption' >&2
  exit 1
fi

docker pause "$publisher_id" >/dev/null
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
  printf '%s\n' 'broker did not become healthy after restart' >&2
  exit 1
fi

subscriber_reconnected=false
for _ in $(seq 1 150); do
  if test "$(grep -c 'subscriber_ready' "$subscriber_log" || true)" -ge 2; then
    subscriber_reconnected=true
    break
  fi
  if ! kill -0 "$subscriber_pid" 2>/dev/null; then
    break
  fi
  sleep 0.2
done
if test "$subscriber_reconnected" != true; then
  cat "$subscriber_log" >&2
  printf '%s\n' 'subscriber did not reconnect after broker restart' >&2
  exit 1
fi

docker unpause "$publisher_id" >/dev/null

publisher_finished=false
for _ in $(seq 1 600); do
  state=$(docker inspect --format '{{.State.Status}}' "$publisher_id")
  if test "$state" = exited; then
    publisher_finished=true
    break
  fi
  sleep 0.2
done
docker logs "$publisher_id" >"$publisher_log" 2>&1 || true
if test "$publisher_finished" != true; then
  cat "$publisher_log" >&2
  printf '%s\n' 'publisher did not finish after broker restart' >&2
  exit 1
fi
if test "$(docker inspect --format '{{.State.ExitCode}}' "$publisher_id")" -ne 0; then
  cat "$publisher_log" >&2
  exit 1
fi

if ! wait "$subscriber_pid"; then
  subscriber_pid=
  cat "$subscriber_log" >&2
  exit 1
fi
subscriber_pid=

grep -q '"event":"mqtt_disconnected"' "$publisher_log"
grep -q '"event":"mqtt_reconnected"' "$publisher_log"
grep -q '"event":"replay_finished"' "$publisher_log"
grep -q '"messages":64' "$publisher_log"
grep -q '"samples":1024' "$publisher_log"
grep -q '"event": "subscriber_complete"' "$subscriber_log"

cat "$subscriber_log"
printf '%s\n' 'Phase 02 broker interruption/reconnection: PASS'
