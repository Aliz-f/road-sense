# Phase 04 implementation report

**Date:** 2026-11-19

**Branch:** `phase/04-analyzer-storage`

**Base:** updated `origin/main` commit
`fb30e0b5aba799d9125f24fd9079457843d1f722` (merged Phase 03)

**Scope:** local Road Analyzer, PostgreSQL persistence, migrations, events,
and integration with the Phase 02/03 laptop Docker Compose stack. Phase 05,
VPS, Rahti, public endpoints, and merging are out of scope.

## Implementation

- `services/road-analyzer` is an independent Python 3.12 microservice with a
  digest-pinned multi-stage image and hash-pinned Paho MQTT/Psycopg
  dependencies. It has configuration, strict schemas, a verified session
  registry, heuristic/event generation, transactional storage, migration and
  health commands, structured logs, and unit/integration helpers.
- The service uses an MQTT 3.1.1 persistent client session, subscribes at QoS 1
  to `roadsense/v1/imu/features`, and manually acknowledges only after a
  validated message is durably stored and any event is acknowledged by the
  broker. Its Paho callback only performs non-blocking insertion into a
  bounded queue. Queue overflow fails closed and leaves the message
  unacknowledged.
- Feature validation requires the exact v1 fields, canonical lowercase UUID,
  immutable provenance, one-second source interval, positive sample count,
  finite non-negative metrics, defined baseline/algorithm, and unique ordered
  quality flags. Duplicate JSON keys and unknown fields are rejected.
- The tracked session registry contains only the three sessions already
  verified in `docs/dataset-profile.md`. It supplies immutable full recording
  bounds, row count, road-category label, and unknown-orientation note that are
  not present in feature v1. Incoming session/sensor/hash/member and
  `session_start + window_index` must match it.
- `0001_analyzer_storage.sql` creates `sessions`, `runs`, `feature_windows`,
  `events`, indexes, foreign keys, checks, and unique idempotency constraints.
  The migration runner serializes with a PostgreSQL advisory lock and records
  each migration checksum in `schema_migrations`; an applied migration cannot
  silently change.
- A feature, its session/run references, and any detected event are written in
  one transaction. Exact duplicate
  `(run_id, window_index, algorithm_version)` content reuses the row. Different
  content or provenance for an existing key raises `ConflictingDataError` and
  is acknowledged as a deterministic rejection rather than overwriting data.
- Event IDs are deterministic UUIDv5 values over run/window/algorithm/rule.
  Event publication is at least once: if the database commit succeeds but
  publication/acknowledgement fails, redelivery republishes the same event ID.
- Compose adds digest-pinned PostgreSQL 16.6, the one-shot migration service,
  Road Analyzer, health checks, test helpers, and the named
  `roadsense-local-postgres-data` volume. PostgreSQL, broker, analyzer, and
  processor publish no host ports. Runtime service roots are read-only and
  local passwords/certificate keys remain ignored.

## Threshold rationale

The configurable Phase 04 rule is inclusive:

```text
vibration_rms_mg >= ANALYZER_VIBRATION_RMS_THRESHOLD_MG
```

The default is `100.0 mg`, with rule version
`roadsense-high-vibration-rms-v1-t100`. `tools/profile_phase04_threshold.py`
recomputed the exact Phase 03 one-second metric over all three private Bosch
recordings without extracting or writing raw samples:

| Session | Windows | RMS p50 / p95 / max (mg) | Windows >= 100 mg |
|---|---:|---:|---:|
| Bumpy gravel | 747 | 89.875 / 237.128 / 408.458 | 315 |
| Paved road 60kmh label | 581 | 52.322 / 82.477 / 163.584 | 9 |
| Highway label | 411 | 89.275 / 117.622 / 149.326 | 111 |

This threshold gives useful demonstration events and separates most of the
verified paved recording from larger deviations. The Highway result also
shows that speed, mounting, and context matter: it is not a road-class rule.
Events are explicitly exploratory vehicle-vibration measurements, not
validated potholes, road defects, comfort limits, or safety classifications.
Changing threshold or semantics requires a new rule version so old and new
events cannot be mistaken for one rule.

Reproduction command:

```sh
python3 tools/profile_phase04_threshold.py \
  --archives data/raw/archives --threshold-mg 100
```

## Commands run

Branch preparation:

```sh
git fetch --prune origin
git switch main
git merge --ff-only origin/main
git switch -c phase/04-analyzer-storage
```

Static/config checks:

```sh
sh -n tools/prepare_phase02_local.sh tests/phase04_e2e.sh
python3 -m compileall -q services/road-analyzer/src services/road-analyzer/tests
./tools/prepare_phase02_local.sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml config --quiet
git diff --check
```

Container build and unit tests:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml --profile test build \
  road-analyzer analyzer-unit-tests analyzer-integration-helper event-subscriber
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml --profile test run --rm \
  --no-deps analyzer-unit-tests
```

Real-data acceptance and earlier-phase regressions:

```sh
./tests/phase04_e2e.sh
./tests/phase03_e2e.sh
./tests/phase02_e2e.sh
./tests/phase02_reconnect_e2e.sh
```

## Actual results

The network-disabled analyzer container ran 27 tests:

```text
Ran 27 tests in 0.014s
OK
```

Coverage includes required/unknown/duplicate JSON fields, UUIDs, timestamps,
finite metrics, quality-flag ordering, verified registry provenance, exact
session anchoring, inclusive threshold behavior, deterministic rule-specific
event IDs, required configuration, bounded queue overflow, validation/conflict
acknowledgement, and publish-before-ack behavior.

`tests/phase04_e2e.sh` replayed the first 1,536 actual Bumpy-gravel Bosch
samples at `REPLAY_RATE=0`. An independent archive reader recalculated all 19
windows and matched stored sample counts, RMS, peak deviation, baseline, and
final `incomplete_window` flag to `1e-12` relative/absolute tolerance. The five
`100 mg` crossings were windows `13,14,15,16,18`; an independent event
subscriber received exactly those deterministic event payloads:

```text
Phase 04 analyzer MQTT interruption/reconnection: PASS
{"event":"phase04_database_verified","event_count":5,
 "event_windows":[13,14,15,16,18],"feature_count":19,
 "run_id":"44444444-4444-4444-8444-444444444444"}
Phase 04 real-data storage and event generation: PASS
Phase 04 exact duplicate idempotency and conflicting duplicate rejection: PASS
Phase 04 PostgreSQL persistence after container recreation: PASS
Phase 04 analyzer/storage acceptance checks: PASS
```

The test stopped and restarted Mosquitto and observed a second analyzer-ready
subscription before replay. It republished stored window 13 exactly: feature
and event row counts remained 19 and 5, and the same event ID was published.
It then changed only the RMS under the same feature key; the analyzer logged
`feature_conflict`, acknowledged the poison message, and left counts/content
unchanged.

The test inspected `docker port` for broker, PostgreSQL, and analyzer and found
no mappings. It then removed all Compose containers and the network without
`--volumes`, recreated PostgreSQL, reapplied migrations (reported
`migration_already_applied`), and independently re-queried the same session,
run, 19 features, and five events. The named volume remains locally for this
persistence evidence; containers and the network were removed.

Earlier-phase regressions passed after the Phase 04 Compose and ACL changes:

```text
Phase 03: Ran 23 tests in 0.015s — OK
Phase 03 real-data feature pipeline and replay-rate invariance: PASS
Phase 03 queue-capacity=1 broker backpressure stress: PASS
Phase 02: Ran 21 tests in 1.046s — OK
authenticated broker rejection check: PASS
anonymous broker rejection check: PASS
Phase 02 real-data MQTT end-to-end: PASS
Phase 02 broker interruption/reconnection: PASS
```

The quick Phase 03 regression compared 256 real samples at unpaced and 10×
replay and reproduced the same four reference windows. The Phase 02 reconnect
regression delivered all 1,024 samples in 64 batches across a broker restart.

## Assumptions and remaining issues

- Feature v1 does not carry replay rate or a run-completion signal. Runs store
  nullable replay rate, observed feature bounds, and status `observed`; the
  analyzer does not invent a completion time/status. A future contract change
  is required for authoritative completed-run state.
- The session registry is reviewed, tracked metadata derived from Phase 00.
  Adding or revising a source requires reinspection and a new hash/session
  mapping; the analyzer deliberately rejects unknown provenance.
- Database persistence precedes event publication, but there is no Phase 04
  outbox dispatcher. A failure between commit and MQTT acknowledgement causes
  safe at-least-once republishing on feature redelivery using the same event
  ID. A failure after commit with no producer redelivery would leave the event
  queryable but not published. An outbox is a future reliability enhancement,
  not a Phase 05 implementation.
- The local development MQTT identity can access all Phase 02–04 topics and
  PostgreSQL uses the Compose database owner. Phase 06 must replace these with
  least-privilege runtime/migration identities and revalidate managed TLS,
  storage, backup, and ingress constraints before deployment.
- No automated PostgreSQL backup/restore is added. The named volume proves
  container-recreation persistence, not backup or disaster recovery.
- The retained local volume can contain only derived Phase 04 test records; no
  raw dataset rows or archives are stored in it or Git.

## Rollback

Stop/remove only this Compose project's containers and network while preserving
the database:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml down --remove-orphans
```

If the owner explicitly wants to discard the local derived database as well,
remove only the named Phase 04 volume after confirming it is no longer needed:

```sh
docker volume rm roadsense-local-postgres-data
```

Optional image-cache cleanup:

```sh
docker image rm roadsense/road-analyzer:phase04-local \
  roadsense/road-analyzer-test:phase04-local
```

## Scope confirmation

No FastAPI, dashboard, Phase 05 code, VPS access, Rahti access, Kubernetes
manifest, public service, DNS/firewall/SSH change, secret, raw archive, package
installation on the host, deployment, merge, or push was performed.
