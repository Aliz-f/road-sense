# Phase 02 implementation report

**Date:** 2026-11-19

**Branch:** `phase/02-replay-mqtt`

**Scope:** local Sensor Replay and Mosquitto only. Phase 03 and all remote work
remain out of scope.

## Implementation

- A Python 3.12 Sensor Replay reads `imu/bosch_imu.csv` directly from the
  private `Bumpy Gravel - imu.tar` bind mount. It verifies the Phase 00 archive
  SHA-256, exact header, UTC source timestamps, strict ordering, and integer
  fields before publishing.
- Payloads implement MQTT raw schema v1 with UUID `run_id`, contiguous
  `sequence_id` and `sample_index`, immutable source provenance, explicit `mg`,
  and preserved source timestamps. Batches default to 64 samples and encoded
  payloads are capped at 131,072 bytes.
- Playback is based on source time. `REPLAY_RATE=1` is recorded speed, positive
  values scale it, and `0` is an unpaced validation mode. SIGINT/SIGTERM use a
  shared stop event; MQTT connection attempts are bounded/retried and QoS 1
  publish acknowledgements are awaited. After startup, only Paho's network
  loop initiates reconnects; publish retries wait for that loop instead of
  racing it with a second `connect()` call.
- Mosquitto 2.0.22 uses a digest-pinned image, anonymous access disabled, a
  generated password file/ACL, and locally generated TLS certificates. It has
  no host-published port and is reachable only on the internal Compose network.
- Python, Dockerfile frontend, Mosquitto, and Paho MQTT inputs are version or
  digest pinned. `.dockerignore` excludes private data, local environment files,
  keys, Git metadata, and generated files from the build context.

## Local preparation and commands

The preparation script reads the ignored Phase 01 dataset path, generates a
random local password plus a short-lived development CA/server certificate, and
writes only ignored files. It automatically replaces a certificate that is
missing or expires within one day.

```sh
./tools/prepare_phase02_local.sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml config --quiet
```

Unit tests:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml --profile test build \
  sensor-replay mqtt-subscriber unit-tests
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml --profile test run --rm \
  --no-deps unit-tests
```

Fast real-data integration and complete recording replay:

```sh
./tests/phase02_e2e.sh
PHASE02_FULL_REPLAY=true ./tests/phase02_e2e.sh
```

Real broker interruption and automatic reconnection:

```sh
./tests/phase02_reconnect_e2e.sh
```

Manual broker/replay/cleanup:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml up -d --wait mqtt-broker
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm \
  -e REPLAY_RATE=10 -e MAX_SAMPLES=1024 sensor-replay
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml down --remove-orphans
```

## Tests and sanitized evidence

The corrected Phase 02 suite was rerun locally on 2026-11-19. The
containerized unit suite covers:

- archive hash/member/header validation and actual source field parsing;
- invalid, non-UTC, duplicate, and non-increasing timestamps;
- blank/non-integer values, sample limits, and bounded batch tails;
- raw schema, UUID/sequence checks, payload byte cap, and contiguous samples;
- replay-rate scheduling, stop behavior, connection retries/exhaustion, and
  shutdown cancellation;
- serialized concurrent startup and the invariant that publish retries never
  invoke a competing MQTT `connect()` after the network loop starts.

Sanitized result:

```text
Ran 19 tests
OK
authenticated broker rejection check: PASS
anonymous broker rejection check: PASS
```

The quick integration used 128 actual samples in two batches. The final full
run read and published the entire verified recording:

```text
replay_finished messages=972 samples=62169
subscriber_complete first_timestamp=2026-10-19T05:51:57.052Z
subscriber_complete last_sample_index=62168 messages=972 samples=62169
Phase 02 real-data MQTT end-to-end: PASS
Phase 02 full-replay cleanup: PASS
```

The interruption test publishes 1,024 actual samples at a paced rate, pauses
the publisher after acknowledged batches, stops and starts the real Mosquitto
container, waits for the independent subscriber to resubscribe, then resumes
the publisher. It requires both publisher disconnect/reconnect events and the
complete contiguous 64-message stream:

```text
mqtt_disconnected
mqtt_reconnected
subscriber_complete messages=64 samples=1024 last_sample_index=1023
Phase 02 broker interruption/reconnection: PASS
```

Final regression summary:

```text
unit tests: 19 passed
quick real-data replay: 2 messages / 128 samples — PASS
broker stop/start replay: 64 messages / 1,024 samples — PASS
full real-data replay: 972 messages / 62,169 samples — PASS
authenticated rejection: PASS
anonymous rejection: PASS
```

## Selecting other verified recordings

The archive name, tar member, SHA-256, and session ID form one provenance
tuple. All four values must be selected together; mixing them is invalid. The
safe tuples and a copyable Compose override are documented in
`services/sensor-replay/README.md`. In particular, Highway uses
`imu/bosch.csv`, while Bumpy gravel and Paved road use
`imu/bosch_imu.csv`. Archive hashing, member lookup, and exact-header checks
fail closed. The three files keep `SENSOR_ID=bosch-xdk-110`; CAN is not
selectable because SPEED units remain unverified.

The independent subscriber validated every unique payload, one stable `run_id`,
contiguous sequence/sample indexes, schema fields, first timestamp, and total
count. The final 25-sample batch was sequence 971. Test cleanup confirmed no
`roadsense-local` container or network remained. Existing unrelated containers
were not stopped or modified.

## Issues and decisions

- Docker Desktop accepted a loopback broker mapping in rendered Compose config
  but did not materialize it while the broker used only an internal network.
  Phase 02 needs no host client, so the mapping was removed. This is safer and
  the separate subscriber connects inside Compose.
- A local credential displayed during port diagnostics was immediately rotated
  with `prepare_phase02_local.sh --force`; it was never tracked or committed.
- Development certificates are intentionally local/short-lived. Phase 06 must
  use approved externally managed certificates and revalidate Rahti ingress;
  this phase makes no claim about remote TLS support.
- The tracked local environment example now points clients at the mounted
  issuing CA, `/run/roadsense/mqtt/ca.crt`, rather than the broker leaf
  certificate.
- Generated images remain in the local Docker cache. Containers and networks
  are removed by test cleanup. Optional image rollback is:

  ```sh
  docker image rm roadsense/sensor-replay:phase02-local \
    roadsense/sensor-replay-test:phase02-local
  ```

## Scope confirmation

No signal processor, analyzer, database, API, dashboard, VPS action, Rahti
action, public endpoint, package installation, or remote deployment was added.
