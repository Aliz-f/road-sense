# Phase 04 implementation and reliability report

**Date:** 2026-11-19

**Branch:** `phase/04-analyzer-storage`

**Scope:** local Docker Compose Road Analyzer, PostgreSQL storage, durable MQTT
delivery, migrations, and Phase 02/03 integration. Phase 05, VPS, Rahti,
deployment, and merging are excluded.

## Implemented design

- The independent Python 3.12 Road Analyzer uses a stable MQTT 3.1.1 client
  identity with `clean_session=false`, subscribes at QoS 1 to
  `roadsense/v1/imu/features`, strictly validates feature v1, and manually
  acknowledges after the database transaction. Invalid or conflicting poison
  messages are logged and acknowledged; transient infrastructure failures are
  retried rather than treated as contract failures.
- Valid features create immutable session/run/feature rows. Exact
  `(run_id, window_index, algorithm_version)` redelivery compares the canonical
  payload SHA-256 and reuses the row. Conflicting feature, run, session, event,
  or outbox content is rejected without overwriting stored data.
- PostgreSQL operations reconnect after `OperationalError`/`InterfaceError`.
  The retried transaction is idempotent, including the ambiguous case where a
  commit succeeded immediately before the connection was lost.
- Detected events and `event_outbox` rows commit in the same transaction. The
  analyzer drains pending rows on startup, after feature storage, and every
  configured poll interval. It publishes QoS 1 before setting `published_at`.
  This removes the former requirement for producer redelivery after a
  database-commit/MQTT failure.
- The unavoidable publish/mark boundary is at-least-once: if MQTT accepts an
  event and the analyzer dies before `published_at` commits, the same
  deterministic `event_id` may be published again. Consumers must collapse
  exact duplicates by `event_id`; no event is silently abandoned.
- `heuristic_rules` binds every `rule_version` to its heuristic type,
  comparison algorithm, event type, severity, and exact threshold. Startup
  fails if an existing version is reused with incompatible configuration.
  Composite foreign keys also bind each event to that configuration and its
  exact feature observation.
- Five immutable/checksummed migrations create the Phase 04 schema, add the
  rule registry/outbox/finite-value checks, and strengthen cross-table
  session, run, feature, observation, and rule integrity. The final upgrade
  migrations make pre-outbox events pending and reconstruct their canonical
  timestamp/float forms so the stored event SHA-256 matches before recovery
  publication. The former failure window is recovered at least once instead
  of being assumed published. Migration execution is serialized by an
  advisory transaction lock.
- Mosquitto persists subscriptions and queued QoS 1 messages to the named
  `roadsense-local-mqtt-data` volume (`mosquitto.db`, one-second autosave). The
  unnecessary `per_listener_settings` mode was removed after testing showed it
  prevented offline message queueing with the pinned Mosquitto 2.0.22 image.
  The existing one-message inflight limit remains the bounded backpressure
  boundary.
- PostgreSQL uses `roadsense-local-postgres-data`; neither database nor broker
  has a host port. Authenticated SQL, not only `pg_isready`, drives the database
  health check.

## PostgreSQL credential lifecycle

`tools/prepare_phase02_local.sh` migrates the former inline password once to
the ignored file `config/environments/local/runtime/postgres/password`. It
creates a password only for a new environment and refuses to invent one when
an existing environment has no recoverable credential. `--force` regenerates
development MQTT/TLS material but never changes this database password.

Explicit rotation requires:

```sh
./tools/rotate_phase04_postgres_password.sh --apply
```

The command writes the future secret atomically to `password.previous` before
`ALTER ROLE`, verifies a new authenticated connection, atomically promotes it
to `password`, and removes the fallback. On interruption, either the current
or fallback file authenticates; analyzer reconnects try both files and reread
them on every connection. Secrets are never printed, tracked, or placed in a
container image.

## Threshold rationale

The inclusive rule is:

```text
vibration_rms_mg >= ANALYZER_VIBRATION_RMS_THRESHOLD_MG
```

The default is `100.0 mg`, version
`roadsense-high-vibration-rms-v1-t100`. The Phase 03 metric was recomputed over
the three private Bosch recordings without extracting or writing raw rows:

| Session | Windows | RMS p50 / p95 / max (mg) | Windows >= 100 mg |
|---|---:|---:|---:|
| Bumpy gravel | 747 | 89.875 / 237.128 / 408.458 | 315 |
| Paved-road 60 km/h label | 581 | 52.322 / 82.477 / 163.584 | 9 |
| Highway label | 411 | 89.275 / 117.622 / 149.326 | 111 |

Reproduce with:

```sh
python3 tools/profile_phase04_threshold.py \
  --archives data/raw/archives --threshold-mg 100
```

The threshold yields useful demonstration events but is not a road-class,
pothole, comfort, defect, or safety rule. Speed, mounting, orientation, and
context are uncontrolled. Any threshold or semantic change requires a new
rule version.

## Commands executed

```sh
sh -n tests/phase04_e2e.sh tools/prepare_phase02_local.sh \
  tools/rotate_phase04_postgres_password.sh
python3 -m compileall -q services/road-analyzer/src \
  services/road-analyzer/tests
./tools/prepare_phase02_local.sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml config --quiet
git diff --check

./tests/phase04_e2e.sh
./tests/phase02_e2e.sh
./tests/phase02_reconnect_e2e.sh
./tests/phase03_e2e.sh
./tests/phase04_e2e.sh
./tests/phase04_e2e.sh
```

The repeated Phase 04 executions reused both existing named volumes. No
`docker compose down --volumes` or database-volume deletion was used.

## Actual results

The analyzer unit runs reported 31 tests and `OK` during the first two complete
end-to-end executions. The final complete run, after adding an explicit
deferred-publish assertion, reported 32 tests in 0.023 s and `OK`. Coverage
includes schema/provenance/config validation, finite values,
threshold/event IDs, bounded callback queues, poison/conflict handling, dynamic
password-file fallback, outbox draining, and completed-event duplicate
suppression.

All three complete Phase 04 executions passed every reliability gate:

```text
Phase 04 forced preparation preserves the existing PostgreSQL credential: PASS
Phase 04 real MUHOS storage, outbox publication, and event generation: PASS
Phase 04 duplicate redelivery is idempotent and conflicting reuse is rejected: PASS
Phase 04 rule versions cannot silently change threshold semantics: PASS
Phase 04 analyzer recovers from a temporary PostgreSQL outage: PASS
Phase 04 persistent MQTT session recovers feature delivery after analyzer restart: PASS
Phase 04 transactional outbox publishes committed events after process restart without feature redelivery: PASS
Phase 04 persistent broker/session recovers queued features across a broker SIGKILL during active delivery: PASS
Phase 04 explicit password rotation and post-restart analyzer recovery: PASS
Phase 04 migrations and data persist across container recreation and repeated existing-volume startup: PASS
```

Final execution 1 used core run
`49287aac-4db2-453e-a3d4-60b8c0938759` and broker-restart run
`758dd0da-6169-437b-9dac-cb58a45a9a07`. Final execution 2, against the same
volumes, used core run `8ea7efca-8061-4e3b-ab8e-56cbf2bcda77` and
broker-restart run `5923a06e-72b7-4b76-b961-ea5ad6d1566d`.
After the legacy-outbox migration was added, final execution 3 reused the same
volumes and passed with core run `290f1694-c056-4d97-a40c-6fb16b24ceb8` and
broker-restart run `7795c235-685b-4195-98ed-87f771f9dfcc`.

For every core/broker run, an independent archive reader recomputed the first
1,536 actual Bumpy-gravel Bosch samples. PostgreSQL contained 19 feature
windows matching sample count, RMS, peak deviation, baseline, and flags to
`1e-12`; events were exactly windows `[13,14,15,16,18]`. All five outbox rows
were published. Exact window-13 redelivery added no row and no second completed
outbox publish; changed RMS under the same key produced `feature_conflict`.

The broker test paused the analyzer, paced the real replay, waited for active
feature production, sent `SIGKILL` to Mosquitto, restarted it from
`mosquitto.db`, resumed the analyzer, and still verified all 19 features and
five events. Separate tests stopped PostgreSQL during delivery, stopped the
analyzer before delivery, and committed a pending outbox event directly before
restart; all recovered without manual data repair.

After migration `0005`, a read-only audit compared every pre-outbox JSON payload
with `events.payload_sha256`, then started the analyzer and checked publication:

```text
{'legacy_events': 5, 'canonical': True, 'published': True}
```

All five legacy payloads were exact canonical duplicates before the recovery
publish; the final migration count and real-data verification also passed on
the existing volume.

Earlier-phase regressions passed:

```text
Phase 02: Ran 21 tests in 1.056s — OK
authenticated broker rejection check: PASS
anonymous broker rejection check: PASS
Phase 02 real-data MQTT end-to-end: PASS (128 samples / 2 batches)
Phase 02 broker interruption/reconnection: PASS (1,024 samples / 64 batches)
Phase 03: Ran 23 tests in 0.013s — OK
Phase 03 real-data feature pipeline and replay-rate invariance: PASS
Phase 03 queue-capacity=1 broker backpressure stress: PASS
```

## Remaining limitations

- MQTT event publication is intentionally at-least-once. The transactional
  outbox prevents loss after database commit, but a crash after broker QoS 1
  acknowledgement and before the outbox mark can republish the same event ID.
- Feature v1 carries neither replay rate nor analyzer run completion. Runs keep
  nullable replay rate, observed bounds, and status `observed`; Phase 04 does
  not invent completion state.
- The local development MQTT account spans Phase 02-04 topics and the database
  owner performs migrations/runtime writes. Phase 06 must introduce and verify
  deployment-specific least-privilege identities.
- Named volumes prove restart/container-recreation persistence, not backup or
  disaster recovery. No backup/restore system is introduced in Phase 04.
- Mosquitto offline queues are bounded at 10,000 messages per client. A longer
  outage that exhausts this configured bound can drop later messages and must
  be handled operationally; the test outage remains well below the bound.

## Rollback

Preserve both durable volumes while removing containers/network:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml down --remove-orphans
```

Deleting `roadsense-local-postgres-data` or `roadsense-local-mqtt-data` is a
separate destructive action and is not part of routine rollback.

## Scope confirmation

No Phase 05/API/dashboard work, VPS/Rahti access, public endpoint, host package
installation, SSH/firewall/DNS change, deployment, merge, raw archive, or
secret was added. All implementation and tests ran on the local laptop with
Docker Compose.
