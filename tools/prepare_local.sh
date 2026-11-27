#!/bin/sh
set -eu

repository_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
input_env="$repository_root/config/environments/local/.env"
runtime_env="$repository_root/config/environments/local/.env.runtime"
runtime_dir="$repository_root/config/environments/local/runtime/mqtt"
postgres_runtime_dir="$repository_root/config/environments/local/runtime/postgres"
postgres_password_file="$postgres_runtime_dir/password"

force=false
if test "${1:-}" = --force; then
  force=true
elif test "$#" -gt 0; then
  printf 'usage: %s [--force]\n' "$0" >&2
  exit 2
fi

test -f "$input_env" || {
  printf '%s\n' 'missing config/environments/local/.env; set ROADSENSE_DATASET_ROOT first' >&2
  exit 1
}
dataset_root=$(sed -n 's/^ROADSENSE_DATASET_ROOT=//p' "$input_env")
test -d "$dataset_root"
test -r "$dataset_root/Bumpy Gravel - imu.tar"
command -v openssl >/dev/null

umask 077
mkdir -p "$runtime_dir" "$postgres_runtime_dir"
chmod 750 "$postgres_runtime_dir"

# Migrate the legacy inline credential once. Thereafter this file is the
# stable source of truth and --force never changes it.
if ! test -s "$postgres_password_file"; then
  legacy_postgres_password=
  if test -s "$runtime_env"; then
    legacy_postgres_password=$(sed -n 's/^POSTGRES_PASSWORD=//p' "$runtime_env")
  fi
  if test -n "$legacy_postgres_password"; then
    printf '%s\n' "$legacy_postgres_password" > "$postgres_password_file"
  elif ! test -s "$runtime_env"; then
    openssl rand -hex 32 > "$postgres_password_file"
  else
    printf '%s\n' 'existing environment has no recoverable PostgreSQL password; refusing to regenerate it' >&2
    exit 1
  fi
  chmod 640 "$postgres_password_file"
fi
chmod 640 "$postgres_password_file"

certificate_valid=false
if test -s "$runtime_dir/ca.crt" && test -s "$runtime_dir/server.crt" && \
  openssl x509 -checkend 86400 -noout -in "$runtime_dir/server.crt" >/dev/null 2>&1 && \
  openssl verify -CAfile "$runtime_dir/ca.crt" "$runtime_dir/server.crt" >/dev/null 2>&1; then
  certificate_valid=true
fi

if test "$force" = true || test "$certificate_valid" != true; then
  openssl req -x509 -newkey rsa:2048 -sha256 -days 365 -nodes \
    -subj '/CN=RoadSense Local Development CA' \
    -addext 'basicConstraints=critical,CA:TRUE' \
    -addext 'keyUsage=critical,keyCertSign,cRLSign' \
    -keyout "$runtime_dir/ca.key" -out "$runtime_dir/ca.crt" >/dev/null 2>&1
  openssl req -newkey rsa:2048 -sha256 -nodes \
    -subj '/CN=mqtt-broker' \
    -keyout "$runtime_dir/server.key" -out "$runtime_dir/server.csr" >/dev/null 2>&1
  {
    printf '%s\n' 'basicConstraints=critical,CA:FALSE'
    printf '%s\n' 'keyUsage=critical,digitalSignature,keyEncipherment'
    printf '%s\n' 'extendedKeyUsage=serverAuth'
    printf '%s\n' 'subjectAltName=DNS:mqtt-broker,DNS:localhost,IP:127.0.0.1'
  } > "$runtime_dir/server.ext"
  openssl x509 -req -sha256 -days 30 \
    -in "$runtime_dir/server.csr" \
    -CA "$runtime_dir/ca.crt" -CAkey "$runtime_dir/ca.key" -CAcreateserial \
    -extfile "$runtime_dir/server.ext" -out "$runtime_dir/server.crt" >/dev/null 2>&1
  chmod 600 "$runtime_dir/ca.key" "$runtime_dir/server.key"
  chmod 644 "$runtime_dir/ca.crt" "$runtime_dir/server.crt"
fi

if test "$force" = true || ! test -s "$runtime_env"; then
  mqtt_password=$(openssl rand -hex 24)
  {
    printf 'ROADSENSE_ENV=local\n'
    printf 'COMPOSE_PROJECT_NAME=roadsense-local\n'
    printf 'LOCAL_UID=%s\n' "$(id -u)"
    printf 'LOCAL_GID=%s\n' "$(id -g)"
    printf 'ROADSENSE_DATASET_ROOT=%s\n' "$dataset_root"
    printf 'ROADSENSE_DATASET_CONTAINER_PATH=/data/archives\n'
    printf 'ROADSENSE_MVP_ARCHIVE="Bumpy Gravel - imu.tar"\n'
    printf 'ROADSENSE_MVP_MEMBER=imu/bosch_imu.csv\n'
    printf 'SOURCE_ARCHIVE_SHA256=91d37ad4de7106d5038ed7bffe1e373db65e0f4771865da8975a216e76ed34f3\n'
    printf 'SESSION_ID=bumpy-gravel-20261019\n'
    printf 'SENSOR_ID=bosch-xdk-110\n'
    printf 'MQTT_HOST=mqtt-broker\n'
    printf 'MQTT_PORT=8883\n'
    printf 'MQTT_BIND_ADDRESS=127.0.0.1\n'
    printf 'MQTT_HOST_PORT=8883\n'
    printf 'MQTT_USERNAME=roadsense-local\n'
    printf 'MQTT_PASSWORD=%s\n' "$mqtt_password"
    printf 'MQTT_TLS_CA_FILE=/run/roadsense/mqtt/ca.crt\n'
    printf 'MQTT_RUNTIME_DIR=%s\n' "$runtime_dir"
    printf 'MQTT_TOPIC=roadsense/v1/imu/raw\n'
    printf 'MQTT_RAW_TOPIC=roadsense/v1/imu/raw\n'
    printf 'MQTT_RUN_COMPLETE_TOPIC=roadsense/v1/imu/run-complete\n'
    printf 'MQTT_FEATURE_TOPIC=roadsense/v1/imu/features\n'
    printf 'MQTT_EVENT_TOPIC=roadsense/v1/events\n'
    printf 'PROCESSOR_MQTT_CLIENT_ID=roadsense-signal-processor-local\n'
    printf 'PROCESSOR_QUEUE_CAPACITY=1024\n'
    printf 'ANALYZER_MQTT_CLIENT_ID=roadsense-road-analyzer-local\n'
    printf 'ANALYZER_QUEUE_CAPACITY=1024\n'
    printf 'ANALYZER_VIBRATION_RMS_THRESHOLD_MG=100.0\n'
    printf 'ANALYZER_RULE_VERSION=roadsense-high-vibration-rms-v1-t100\n'
    printf 'ANALYZER_SESSION_REGISTRY_FILE=/app/session-registry.json\n'
    printf 'POSTGRES_HOST=postgres\n'
    printf 'POSTGRES_PORT=5432\n'
    printf 'POSTGRES_DB=roadsense\n'
    printf 'POSTGRES_USER=roadsense\n'
    printf 'POSTGRES_PASSWORD_FILE=/run/roadsense/postgres/password\n'
    printf 'POSTGRES_PREVIOUS_PASSWORD_FILE=/run/roadsense/postgres/password.previous\n'
    printf 'POSTGRES_CONNECT_TIMEOUT_SECONDS=5\n'
    printf 'POSTGRES_CONNECT_RETRIES=30\n'
    printf 'MQTT_CONNECT_RETRIES=10\n'
    printf 'MQTT_CONNECT_TIMEOUT_SECONDS=10\n'
    printf 'MQTT_PUBLISH_TIMEOUT_SECONDS=10\n'
    printf 'BATCH_SIZE=64\n'
    printf 'MAX_PAYLOAD_BYTES=131072\n'
    printf 'MAX_SAMPLES=0\n'
    printf 'REPLAY_RATE=1.0\n'
  } > "$runtime_env"
  chmod 600 "$runtime_env"
fi

ensure_setting() {
  setting_name=$1
  setting_value=$2
  if ! grep -q "^${setting_name}=" "$runtime_env"; then
    printf '%s=%s\n' "$setting_name" "$setting_value" >> "$runtime_env"
  fi
}

ensure_setting MQTT_EVENT_TOPIC roadsense/v1/events
ensure_setting ANALYZER_MQTT_CLIENT_ID roadsense-road-analyzer-local
ensure_setting ANALYZER_QUEUE_CAPACITY 1024
ensure_setting ANALYZER_VIBRATION_RMS_THRESHOLD_MG 100.0
ensure_setting ANALYZER_RULE_VERSION roadsense-high-vibration-rms-v1-t100
ensure_setting ANALYZER_SESSION_REGISTRY_FILE /app/session-registry.json
ensure_setting POSTGRES_HOST postgres
ensure_setting POSTGRES_PORT 5432
ensure_setting POSTGRES_DB roadsense
ensure_setting POSTGRES_USER roadsense
sed -i '/^POSTGRES_PASSWORD=/d' "$runtime_env"
ensure_setting POSTGRES_PASSWORD_FILE /run/roadsense/postgres/password
ensure_setting POSTGRES_PREVIOUS_PASSWORD_FILE /run/roadsense/postgres/password.previous
ensure_setting POSTGRES_CONNECT_TIMEOUT_SECONDS 5
ensure_setting POSTGRES_CONNECT_RETRIES 30
ensure_setting POSTGRES_CONNECT_RETRY_DELAY_SECONDS 1
ensure_setting ANALYZER_OUTBOX_POLL_SECONDS 1
chmod 600 "$runtime_env"

openssl verify -CAfile "$runtime_dir/ca.crt" "$runtime_dir/server.crt" >/dev/null
printf '%s\n' 'Local credentials and TLS material: ready (ignored by Git)'
