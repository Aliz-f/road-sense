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
