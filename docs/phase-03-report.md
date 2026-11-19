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
  publishes QoS 1 payloads to `roadsense/v1/imu/features`. MQTT callbacks put
  messages onto a bounded queue; calculation and acknowledged feature
  publication run outside Paho's network thread. Manual raw-message
  acknowledgement occurs after processing or a deterministic validation
  rejection.
- Each `run_id` has isolated state. One-second half-open windows are anchored
  at that run's first accepted source timestamp. Wall-clock arrival time and
  replay rate are never inputs.
- For every accepted vector the service computes
  `sqrt(x² + y² + z²)` in mg, the window median magnitude, RMS deviation from
  that median, and peak absolute deviation. This standard-library streaming
  implementation needs no NumPy array allocation and follows the v1 contract
  directly.
- Complete windows publish when a later source-time window begins. On graceful
  shutdown, the remaining window publishes with `incomplete_window`; an idle
  wall-clock timeout is deliberately not treated as a run boundary.
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
- Feature keys are `(run_id, window_index, algorithm_version)`. Phase 04 must
  preserve the same idempotency rule when persistence is introduced.

## Compose and configuration

`infrastructure/compose/local.compose.yaml` adds `signal-processor`,
`feature-subscriber`, and `processor-unit-tests`. Runtime containers use a
read-only root filesystem, dropped capabilities, no-new-privileges, the
internal Compose network, and no published host ports. Mosquitto's local ACL
now permits the authenticated development identity to read/write both raw and
feature topics. Credentials, private dataset paths, and local TLS keys remain
in ignored files.

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

The network-disabled container suite ran 18 tests:

```text
Ran 18 tests
OK
```

Coverage includes hand-calculated median/RMS/peak values, rotated vectors,
half-open window boundaries, the strict `>18 ms` gap threshold, missing sample
and sequence IDs, exact and conflicting duplicates, invalid samples,
non-monotonic timestamps, metadata/unit rejection, final partial windows, and
delivery-timing invariance. Invalid records retain their source order and, when
their timestamp remains valid, flag their own source-time window rather than an
earlier window in a spanning batch.

The integration test replayed the first 256 real Bumpy-gravel Bosch samples at
`REPLAY_RATE=0` and `REPLAY_RATE=10`. Both runs produced byte-equivalent
feature content except for the intentionally different run IDs. A separate
standard-library reference reader opened the private tar directly and matched:

| Window | Samples | Baseline mg | RMS mg | Peak deviation mg |
|---:|---:|---:|---:|---:|
| 0 | 84 | 1042.0746134392768 | 4.511680987386085 | 12.296481995420663 |
| 1 | 83 | 1044.1546820275241 | 4.0008108092020676 | 11.138709256531683 |
| 2 | 83 | 1043.3369542003197 | 4.059246563386642 | 8.890207585575354 |

Sanitized result:

```text
phase03_reference_verified windows=3
Phase 03 real-data feature pipeline and replay-rate invariance: PASS
```

The final full test sent all 62,169 verified source rows through Sensor Replay,
Mosquitto, and Signal Processor. The independent feature subscriber validated
746 completed windows (`0…745`). A subscribed graceful stop then validated the
final partial window:

```text
feature_subscriber_complete feature_count=746 first_window_index=0 last_window_index=745
Phase 03 full-recording feature delivery: PASS
feature_subscriber_complete feature_count=1 first_window_index=746 last_window_index=746
final window sample_count=45 quality_flags=[incomplete_window]
Phase 03 graceful final-window flush: PASS
```

The existing Phase 02 regression was rerun after the Compose/ACL changes:

```text
Ran 19 tests
authenticated broker rejection check: PASS
anonymous broker rejection check: PASS
subscriber_complete messages=2 samples=128
Phase 02 real-data MQTT end-to-end: PASS
```

The test also asserted that broker and processor containers had no published
ports. Cleanup removed the Phase 03 Compose containers and internal network;
unrelated local Docker workloads were not modified.

## Remaining issues and decisions

- The raw v1 contract has no explicit end-of-run control message. The processor
  therefore flushes its last window only on graceful shutdown. Adding a
  provenance-bound run-complete message is a future contract decision; using a
  wall-clock idle timeout would violate replay-rate invariance.
- Window zero is anchored at the first accepted sample. Normal Sensor Replay
  starts at `sample_index=0`. If the initial batch is permanently missing, the
  processor flags the sequence/sample gap but cannot reconstruct the original
  session anchor because raw v1 does not carry it.
- Active run state and duplicate caches are in memory. A processor restart
  during an unfinished run requires replaying that recording with a new
  `run_id`; durable recovery is not claimed. Phase 04 persistence must not be
  assumed to solve this unless processor checkpointing or a replay protocol is
  explicitly designed. Without an end-of-run control message, completed run
  caches also are not automatically evicted; long-lived deployments need a
  bounded retention/checkpoint policy.
- The single local development MQTT identity has access to both topics. Phase
  06 must create least-privilege producer/consumer identities and revalidate
  externally managed TLS and Rahti ingress before any deployment.
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
