#!/usr/bin/env bash
# Generates development/demo TLS and credentials LOCALLY only; never creates Rahti Secrets.
set -euo pipefail
if [[ ${1:-} != "--local-only" || $# != 3 ]]; then
  echo "Usage: $0 --local-only MQTT_PUBLIC_HOST PRIVATE_OUTPUT_DIR" >&2
  exit 2
fi
host=$2
dir=$3
if [[ ! $host =~ ^[a-zA-Z0-9.-]+$ || $host != *.* ]]; then
  echo "Specify the real DNS hostname of the planned MQTT TLS endpoint" >&2
  exit 2
fi
for command in openssl python3 docker; do command -v "$command" >/dev/null || { echo "missing $command" >&2; exit 1; }; done
if [[ -e $dir && -n $(find "$dir" -mindepth 1 -maxdepth 1 -print -quit) ]]; then
  echo "refusing to overwrite populated secret directory: $dir" >&2
  exit 1
fi
umask 077
mkdir -p "$dir"
chmod 700 "$dir"
openssl rand -hex 24 > "$dir/mqtt-password"
openssl rand -hex 32 > "$dir/postgres-password"
openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
  -subj "/CN=RoadSense Phase06 Private CA" \
  -addext "basicConstraints=critical,CA:TRUE" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -keyout "$dir/ca.key" -out "$dir/ca.crt" >/dev/null 2>&1
openssl req -newkey rsa:3072 -sha256 -nodes -subj "/CN=$host" \
  -keyout "$dir/server.key" -out "$dir/server.csr" >/dev/null 2>&1
cat > "$dir/server.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:$host,DNS:mqtt-broker
EOF
openssl x509 -req -sha256 -days 90 \
  -in "$dir/server.csr" -CA "$dir/ca.crt" -CAkey "$dir/ca.key" \
  -CAcreateserial -extfile "$dir/server.ext" \
  -out "$dir/server.crt" >/dev/null 2>&1
python3 - "$dir" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1])
(root/"password_file").write_text(
    "roadsense-remote:"+(root/"mqtt-password").read_text().strip()+"\n", encoding="utf-8"
)
PY
# Hash the broker password file. DO NOT place plaintext passwords in shell args.
docker run --rm --user "$(id -u):$(id -g)" --entrypoint mosquitto_passwd \
  -v "$(realpath "$dir"):/secrets:rw" \
  eclipse-mosquitto:2.0.22@sha256:81a6193ae693942a3231cd3ac52875b02b7e3a19da671b2fb4b55cc874c5b279 \
  -U /secrets/password_file >/dev/null
chmod 600 "$dir"/* || true
openssl verify -CAfile "$dir/ca.crt" "$dir/server.crt" >/dev/null
echo "Generated private demo materials locally: $dir"
echo "Never commit files or copy ca.key to VPS/Rahti."
