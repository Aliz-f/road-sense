# Phase 03 implementation report

**Date:** 2026-11-19

**Branch:** `phase/03-signal-processing`

**Scope:** local Signal Processor integration with the Phase 02 Sensor Replay
and Mosquitto stack. Phase 04 and all remote work remain out of scope.

## Implementation

- `services/signal-processor` is an independent Python 3.12 microservice with
  its own digest-pinned multi-stage image, hashed Paho MQTT dependency,
  environment validation, raw/feature schema code, processor, structured
  events, unit tests, and an independent feature test subscriber.
- It subscribes at QoS 1 to `roadsense/v1/imu/raw` over authenticated TLS and
  `roadsense/v1/imu/run-complete` and publishes QoS 1 payloads to
  `roadsense/v1/imu/features`. The Paho callback uses non-blocking insertion
  into a bounded queue; calculation and acknowledged feature publication run
  outside the network thread. Manual acknowledgement occurs after processing
  or a deterministic validation rejection.
- Mosquitto allows only one unacknowledged QoS message per subscriber. This is
  the pressure boundary: it does not deliver the next message until the worker
  acknowledges the current one. If the queue is nevertheless full, the
  callback records a fatal `processor_queue_overflow`, leaves the message
  unacknowledged, and returns immediately so the Paho network thread cannot
  deadlock or silently discard input.
- Each `run_id` has isolated state. One-second half-open windows are anchored
  at that run's first accepted source timestamp. Wall-clock arrival time and
  replay rate are never inputs.
- For every accepted vector the service computes
  `sqrt(x² + y² + z²)` in mg, the window median magnitude, RMS deviation from
  that median, and peak absolute deviation. This standard-library streaming
  implementation needs no NumPy array allocation and follows the v1 contract
  directly.
- Complete windows publish when a later source-time window begins. After all
  raw QoS 1 publishes are acknowledged, Sensor Replay sends a count- and
  provenance-bound completion message. The processor tolerates cross-topic
  reordering by waiting for all declared sequences, publishes the remaining
  window with `incomplete_window`, and stays running. Graceful shutdown remains
  a fallback; wall-clock idle time is not treated as a run boundary.
- Feature payloads preserve archive hash/member provenance and use
  `algorithm_version=roadsense-vibration-v1`. They are exploratory vehicle
  vibration measurements, not calibrated vertical acceleration, validated
  potholes, or safety classifications.

## Validation and quality handling

- Top-level raw schema/version, UUID, session/sensor/provenance strings,
  lowercase archive SHA-256, sequence ID, `mg` unit, and non-empty sample array
  are validated before processing.
- Invalid individual samples are skipped and flagged; numeric values are never
  coerced. Non-monotonic source times are skipped and flagged.
- An adjacent source interval greater than 18 ms, a missing batch sequence, or
  a missing sample index sets `source_time_gap`. No missing measurement is
  interpolated.
- Identical `(run_id, sequence_id)` QoS 1 deliveries and identical sample
  duplicates are ignored. Conflicting reuse is rejected. Session, sensor, and
  provenance metadata may not change within a run.
- An identical `(run_id, run_complete)` control redelivery is ignored;
  conflicting completion content is rejected. Counts must agree with
  zero-based final sequence and sample indices. An early completion is held
  until every declared raw sequence has arrived.
- Feature keys are `(run_id, window_index, algorithm_version)`. Phase 04 must
  preserve the same idempotency rule when persistence is introduced.

## Compose and configuration

`infrastructure/compose/local.compose.yaml` adds `signal-processor`,
`feature-subscriber`, and `processor-unit-tests`. Runtime containers use a
read-only root filesystem, dropped capabilities, no-new-privileges, the
internal Compose network, and no published host ports. Mosquitto's local ACL
now permits the authenticated development identity to read/write raw,
run-complete, and feature topics. `max_inflight_messages 1` enforces the
per-subscriber QoS pressure boundary. Credentials, private dataset paths, and
local TLS keys remain in ignored files.

Preparation and rendered-config check:

```sh
./tools/prepare_phase02_local.sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml config --quiet
```

Containerized unit tests:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml --profile test build \
  signal-processor feature-subscriber processor-unit-tests
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml --profile test run --rm \
  --no-deps processor-unit-tests
```

Real-data pipeline, replay-rate comparison, and full recording:

```sh
./tests/phase03_e2e.sh
PHASE03_FULL_REPLAY=true ./tests/phase03_e2e.sh
```

Phase 02 regressions:

```sh
./tests/phase02_e2e.sh
./tests/phase02_reconnect_e2e.sh
```

Manual local lifecycle:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml up -d --wait \
  mqtt-broker signal-processor
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm \
  -e REPLAY_RATE=10 -e MAX_SAMPLES=1024 sensor-replay
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml down --remove-orphans
```

## Actual results

The network-disabled Signal Processor container suite ran 23 tests:

```text
Ran 23 tests in 0.010s
OK
```

Coverage includes hand-calculated median/RMS/peak values, rotated vectors,
half-open window boundaries, the strict `>18 ms` gap threshold, missing sample
and sequence IDs, exact and conflicting duplicates, invalid samples,
non-monotonic timestamps, metadata/unit rejection, early, duplicate, and
conflicting run completion, final partial windows, delivery-timing invariance,
and a pre-filled capacity-one queue. The queue test measured the callback
returning in under 0.1 seconds, with the existing message unchanged and a
fatal overflow state set. Invalid records retain their source order and, when
their timestamp remains valid, flag their own source-time window rather than
an earlier window in a spanning batch.

The integration test replayed the first 256 real Bumpy-gravel Bosch samples at
`REPLAY_RATE=0` and `REPLAY_RATE=10`. Both runs produced byte-equivalent
feature content except for the intentionally different run IDs. A separate
standard-library reference reader opened the private tar directly and matched:

| Window | Samples | Baseline mg | RMS mg | Peak deviation mg |
|---:|---:|---:|---:|---:|
| 0 | 84 | 1042.0746134392768 | 4.511680987386085 | 12.296481995420663 |
| 1 | 83 | 1044.1546820275241 | 4.0008108092020676 | 11.138709256531683 |
| 2 | 83 | 1043.3369542003197 | 4.059246563386642 | 8.890207585575354 |
| 3 | 6 | 1045.2428029568473 | 3.1049592282359217 | 5.2341491466975185 |

Sanitized result:

```text
phase03_reference_verified windows=4
Phase 03 real-data feature pipeline and replay-rate invariance: PASS
Phase 03 queue-capacity=1 broker backpressure stress: PASS
```

For both quick replays the final six-sample window carried
`quality_flags=[incomplete_window]`, and the processor container remained
running after completion. The Compose test rendered and inspected
`PROCESSOR_QUEUE_CAPACITY=1` and found no `processor_queue_overflow` event.

The full test sent all 62,169 verified source rows through Sensor Replay,
Mosquitto, and Signal Processor and required Sensor Replay's completion event.
The independent feature subscriber received all 747 windows (`0…746`) in one
subscription; window 746 contained 45 samples and `incomplete_window`. The
processor remained running:

```text
feature_subscriber_complete feature_count=747 first_window_index=0 last_window_index=746 last_sample_count=45 last_quality_flags=[incomplete_window]
Phase 03 full-recording end-of-run feature delivery: PASS
```

Both Phase 02 regressions were rerun after the replay and broker changes. The
Sensor Replay suite now contains 21 tests, including completion-schema tests:

```text
Ran 21 tests in 1.064s
authenticated broker rejection check: PASS
anonymous broker rejection check: PASS
subscriber_complete messages=2 samples=128
Phase 02 real-data MQTT end-to-end: PASS
subscriber_complete messages=64 samples=1024
Phase 02 broker interruption/reconnection: PASS
```

During the reconnection test Mosquitto was stopped and restarted while Sensor
Replay was active; the subscriber received all 1,024 samples. The Phase 03
test also asserted that broker and processor containers had no published ports.
Each script's cleanup removed its Compose containers and internal network;
unrelated local Docker workloads were not modified.

## Remaining issues and decisions

- The completion protocol covers successful non-empty Sensor Replay runs. An
  interrupted producer deliberately sends no completion, so its open run is
  retained until replay/recovery or graceful processor shutdown; no wall-clock
  timeout is used because that would violate replay-rate invariance.
- Window zero is anchored at the first accepted sample. Normal Sensor Replay
  starts at `sample_index=0`. If the initial batch is permanently missing, the
  processor flags the sequence/sample gap but cannot reconstruct the original
  session anchor because raw v1 does not carry it.
- Active run state and duplicate caches are in memory. A processor restart
  during an unfinished run requires replaying that recording with a new
  `run_id`; durable recovery is not claimed. Phase 04 persistence must not be
  assumed to solve this unless processor checkpointing or a replay protocol is
  explicitly designed. Completed run caches are not automatically evicted;
  long-lived deployments need a bounded retention/checkpoint policy.
- The single local development MQTT identity has access to all three topics.
  Phase 06 must create least-privilege producer/consumer identities and
  revalidate externally managed TLS and Rahti ingress before any deployment.
- The full test leaves only locally cached images. Optional rollback is:

  ```sh
  docker compose --env-file config/environments/local/.env.phase02 \
    -f infrastructure/compose/local.compose.yaml down --remove-orphans
  docker image rm roadsense/signal-processor:phase03-local \
    roadsense/signal-processor-test:phase03-local
  ```

## Scope confirmation

No analyzer, database, persistence, API, dashboard, Phase 04 service, VPS
action, Rahti action, public endpoint, local package installation, or remote
deployment was added.
