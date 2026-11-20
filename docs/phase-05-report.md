# Phase 05 API and dashboard implementation report

**Date:** 2026-11-20

**Branch:** `phase/05-api-dashboard`

**Scope:** local-laptop FastAPI, Streamlit/Plotly, complete Docker Compose
integration, real MUHOS validation, and Phases 02–04 regressions. VPS, Rahti,
Phase 06, deployment, and merging are excluded.

The official course
[`Final-Project/README.md`](https://gitlab.com/sdx-oulu/2024/hw-and-project/-/blob/main/Final-Project/README.md)
was rechecked on 2026-11-20. It
still requires a dockerized, non-monolithic application demonstrating local and
Rahti microservice interaction, submission material in `Final-Project/`, an
architecture image, and a camera/microphone video of at most ten minutes. This
GitHub development branch is not claimed to satisfy the later GitLab hand-in or
Rahti demonstration requirements.

## Implemented design

- A separate Python 3.12 FastAPI container provides typed, read-only endpoints
  for liveness, database readiness, sessions, runs, feature windows, threshold
  events, and aggregate processing status. Collection endpoints return bounded
  `limit`/`offset` pages with `count` and `total`.
- API path UUIDs, response timestamps, enums, metrics, counts, provenance, and
  pagination are validated with Pydantic. Unknown valid run IDs return 404;
  malformed IDs and pagination return 422. PostgreSQL statements are fixed and
  parameterized and every API transaction is set read-only. Run feature and
  event counts use separate correlated indexed subqueries, avoiding the former
  feature/event cross-product while retaining filtering and pagination.
- FastAPI rereads the current PostgreSQL password file for each connection and
  tries the optional `password.previous` fallback after an operational login
  failure. This matches Phase 04 rotation semantics; strict parsing rejects
  empty or multi-line secret files.
- A separate Streamlit/Plotly container uses HTTP FastAPI only. It supports
  recording and run selection, source-time RMS and peak-deviation traces,
  exploratory event overlays, aggregate processing status, event details, and
  immutable source provenance. The UI states that results are not validated
  potholes, defects, comfort ratings, or safety classifications.
- API and dashboard run with read-only root filesystems, dropped Linux
  capabilities, `no-new-privileges`, tmpfs scratch space, independent health
  checks, and non-root users. Pinned base image digests and exact direct Python
  dependency versions are used.
- Compose retains the internal `roadsense` network for MQTT/PostgreSQL and adds
  a restricted `browser` network for API/dashboard HTTP. Only
  `127.0.0.1:8000` and `127.0.0.1:8501` are published. The split is necessary
  on the verified Docker engine because a container attached only to an
  `internal` network receives no effective host port publication.
- No database migration was needed. Phase 05 reads the immutable Phase 04
  schema and preserves the truthful run status `observed`; it does not invent a
  completion state because the analyzer has no run-completion input contract.

## Local operation

Prepare ignored local credentials and start the six long-running components:

```sh
./tools/prepare_phase02_local.sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml up --build -d --wait \
  mqtt-broker postgres signal-processor road-analyzer api dashboard
```

Run the one-shot seventh component against the private read-only MUHOS mount:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm sensor-replay
```

Open the dashboard at `http://127.0.0.1:8501`, the API documentation at
`http://127.0.0.1:8000/docs`, or inspect sanitized service logs:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml ps
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml logs --tail=100 \
  mqtt-broker signal-processor road-analyzer postgres api dashboard
```

Routine shutdown preserves both named data volumes:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml down --remove-orphans
```

Do not add `--volumes` unless permanent local data deletion is explicitly
intended and approved.

## Commands executed

```sh
python3 -m compileall -q services/api/src services/api/tests \
  services/dashboard/src services/dashboard/tests tests/verify_phase05_api.py
sh -n tests/phase05_e2e.sh
git diff --check
./tools/prepare_phase02_local.sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml config --quiet

./tests/phase05_e2e.sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm --no-deps api-unit-tests
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm --no-deps dashboard-smoke-tests
./tests/phase02_e2e.sh
./tests/phase02_reconnect_e2e.sh
./tests/phase03_e2e.sh
./tests/phase04_e2e.sh
```

## Actual Phase 05 results

The successful complete run used two real MUHOS archive members, each limited
to the first 1,536 source rows with 64-sample MQTT batches and unpaced replay:

| Recording | Run ID | Features | Events |
|---|---|---:|---:|
| Bumpy gravel | `56004c37-01bd-42b1-bc00-b8e4541d7901` | 19 | 5 at windows `[13, 14, 15, 16, 18]` |
| Paved road 60kmh | `d23313c4-355d-4264-9893-6fa00ab811a3` | 19 | 0 |

Both archives remained mounted read-only and no raw row or archive was copied
into Git. An independent standard-library reader derived the expected event
windows from the configured inclusive RMS threshold and recomputed every
feature window. The API matched sample counts, source bounds, quality flags,
median baselines, RMS, and peak deviations to `1e-12` for both recordings. It
also returned the correct independent feature/event counts from the paginated
and session-filtered runs endpoint, with a zero pending-outbox count.

The API suite reported 11 tests and `OK`. In addition to all endpoint and
validation contracts, it covers strict password-file parsing, per-attempt file
rereads, current-to-previous fallback, read-only transactions, and the
non-cross-product runs query shape. The dashboard suite reported 7 tests and
`OK`. Its successful Streamlit path uses representative two-recording API data
to exercise recording/run selection, four status statistics, two metric
traces, the event overlay, and the high-vibration event table. It also covers
client paging/Plotly behavior and API/status/run-list failure states.
Final isolated pre-commit reruns also passed: API 11 tests in 0.114 seconds and
dashboard 7 tests in 1.567 seconds.

The Compose gate staged a future secret in `password.previous`, changed the
database role, and deliberately stopped before promotion. After an API restart,
readiness succeeded through the fallback. The recovery helper then verified
the active credential, atomically promoted it, removed the fallback, and
confirmed readiness again. No password was logged.

The dashboard integration client loaded both real runs. Bumpy gravel produced
two metric traces plus an event-marker trace; Paved road produced the two
metric traces and the truthful empty-event state. With the API stopped, client
access failed as expected while the Streamlit health endpoint remained HTTP
200; the API restarted and recovered.

Sanitized successful output:

```text
Ran 11 tests in 0.098s — OK
Ran 7 tests in 0.777s — OK
Phase 05 interrupted credential rotation staged after database change: PASS
Phase 05 API password-file fallback during interrupted rotation: PASS
Phase 05 credential rotation fixture recovered: PASS
{"event":"phase05_api_reference_verified","events":5,"features":19,
 "run_id":"56004c37-01bd-42b1-bc00-b8e4541d7901"}
{"event":"phase05_api_reference_verified","events":0,"features":19,
 "run_id":"d23313c4-355d-4264-9893-6fa00ab811a3"}
Phase 05 dashboard API client and Plotly real-data rendering: PASS (twice)
Phase 05 dashboard handles API service failure and recovery: PASS
Phase 05 full local real-MUHOS pipeline, API, and dashboard smoke: PASS
```

The integration gate also confirmed that API and dashboard health endpoints
and the Streamlit root returned HTTP 200, all six persistent components were
running, API/dashboard mapped only to loopback, and MQTT, PostgreSQL, processor,
and analyzer had no host port.

An actual local Chromium session was opened against `127.0.0.1:8501` after the
gate. Its rendered DOM showed the Paved road recording and run above, 19
feature windows, zero events, both Plotly series, and the empty-event message.
The persisted test volume also exposed the expected aggregate statistics. With
the API container intentionally stopped and the page reloaded, Chromium showed
the explicit `RoadSense API is unavailable` error; the container was then
restarted. The successful Bumpy event display and selector changes are covered
by the Streamlit successful-path test and the same real API data was verified
by the integration client.

## Earlier-phase regression results

All requested earlier gates passed after the Compose changes:

```text
Phase 02: Ran 21 tests in 1.065s — OK
authenticated broker rejection check: PASS
anonymous broker rejection check: PASS
Phase 02 real-data MQTT end-to-end: PASS (128 samples / 2 batches)
Phase 02 broker interruption/reconnection: PASS (1,024 samples / 64 batches)

Phase 03: Ran 23 tests in 0.017s — OK
Phase 03 real-data feature pipeline and replay-rate invariance: PASS
Phase 03 queue-capacity=1 broker backpressure stress: PASS

Phase 04: Ran 32 tests in 0.027s — OK
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

The final Phase 04 run used core run
`d8bb4fa9-8ba1-45e4-92c2-0574c8e1a376` and broker-restart run
`3ceb3953-c132-49e8-8aac-5ac2db68fa5d`. Both retained their 19 features and
five events across the tested failure/recreation paths. Phase 04 also rotated
the ignored local PostgreSQL credential successfully before final volume
recreation checks.

## Remaining limitations

- Phase 04 run status remains `observed`, not `complete`, because the analyzer
  does not consume the replay-completion control topic. The API and dashboard
  expose this accurately.
- API/dashboard authentication and external HTTPS are intentionally absent from
  the loopback-only local Phase 05 stack. Phase 06 must design and verify remote
  access controls and TLS before exposing either component.
- Dashboard charts load a complete selected run through bounded 500-row API
  pages. This is appropriate for the verified recordings but is not
  downsampling or streaming for arbitrarily large future runs.
- The local browser check inspected the rendered Chromium DOM rather than
  maintaining a screenshot artifact; the deterministic Streamlit test is the
  automated regression for widget selection and high-vibration table content.
- MQTT event publication remains at least once, so a consumer must collapse an
  exact duplicate by deterministic `event_id`.
- Existing named volumes demonstrate persistence and restart recovery, not
  backup/restore disaster recovery.

## Scope confirmation

No VPS or Rahti endpoint was contacted, no public service was exposed, no host
package was installed, no SSH/firewall/DNS setting was changed, no raw archive
or secret was tracked, no Phase 06 artifact was implemented, and no branch was
merged. All application and regression validation ran locally through Docker
Compose.
