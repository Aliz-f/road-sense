# Sensor Replay

Phase 02 implements a standalone Python service that reads the verified Bosch
CSV directly from its private MUHOS tar archive and publishes bounded MQTT v1
batches to `roadsense/v1/imu/raw`.

The service verifies the archive SHA-256, exact CSV header, UTC timestamps,
strict source-time ordering, and integer sensor values before publishing. Each
run receives a UUID `run_id`; batches and samples carry contiguous
`sequence_id` and `sample_index` values. QoS 1 acknowledgements are awaited.

Configuration is environment-only. `REPLAY_RATE=1` follows recorded source
time, values above one accelerate playback, values between zero and one slow
it, and `0` disables pacing for tests. `MAX_SAMPLES=0` means the complete
recording. Raw archives are mounted read-only and never copied into the image.

Local execution uses the TLS/authenticated broker in
`infrastructure/compose/local.compose.yaml`. Prepare ignored credentials first:

```sh
./tools/prepare_phase02_local.sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml up -d --wait mqtt-broker
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm \
  -e REPLAY_RATE=10 -e MAX_SAMPLES=1024 sensor-replay
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml down --remove-orphans
```

See `../../docs/phase-02-report.md` for test commands and evidence. This
service is local-only until Phase 06.

## Selecting another verified IMU recording

Treat `ROADSENSE_MVP_ARCHIVE`, `ROADSENSE_MVP_MEMBER`,
`SOURCE_ARCHIVE_SHA256`, and `SESSION_ID` as one immutable provenance tuple.
Never change only the filename or reuse a session ID with a different hash.
The three Phase 00 verified tuples are:

| Recording | Archive | Member | SHA-256 | Session ID |
|---|---|---|---|---|
| Bumpy gravel (default) | `Bumpy Gravel - imu.tar` | `imu/bosch_imu.csv` | `91d37ad4de7106d5038ed7bffe1e373db65e0f4771865da8975a216e76ed34f3` | `bumpy-gravel-20261019` |
| Paved road 60 km/h | `Paved Road 60kmh - imu.tar` | `imu/bosch_imu.csv` | `cf3d0002573f1ecaa021034a3a20dee6cbb21a47989026d8b4ed0c8a81b7c6a4` | `paved-road-60kmh-20261007` |
| Highway | `Highway - imu.tar` | `imu/bosch.csv` | `d80eb161b896819851ed2d3aeea38da977c98a836096b31d9f6a5e8af193c903` | `highway-20261007` |

Override all four values together for one Compose run. For example:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm \
  -e 'ROADSENSE_MVP_ARCHIVE=Paved Road 60kmh - imu.tar' \
  -e ROADSENSE_MVP_MEMBER=imu/bosch_imu.csv \
  -e SOURCE_ARCHIVE_SHA256=cf3d0002573f1ecaa021034a3a20dee6cbb21a47989026d8b4ed0c8a81b7c6a4 \
  -e SESSION_ID=paved-road-60kmh-20261007 \
  sensor-replay
```

The replay rejects an archive whose bytes do not match the selected hash and
rejects a missing member or header drift. Keep `SENSOR_ID=bosch-xdk-110` for
these three Bosch files. CAN archives remain excluded because their SPEED unit
is not verified.
