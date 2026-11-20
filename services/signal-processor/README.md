# Signal Processor

Phase 03 implements an independent MQTT microservice that consumes validated
raw Bosch IMU batches from `roadsense/v1/imu/raw`, groups accepted samples into
one-second half-open source-time windows, and publishes feature payloads to
`roadsense/v1/imu/features`. It also consumes the provenance-bound
`roadsense/v1/imu/run-complete` control topic.

For every accepted acceleration vector it computes magnitude in mg, uses the
window median magnitude as the orientation-robust baseline, and publishes RMS
and peak absolute deviation from that baseline. These are exploratory vehicle
vibration features, not pothole, road-safety, or calibrated vertical-motion
classifications.

The processor:

- validates schema version, identifiers, provenance, units, timestamps, and
  numeric acceleration fields;
- ignores byte-equivalent QoS 1 batch duplicates and identical sample
  duplicates, while rejecting conflicting reuse of an idempotency key;
- does not interpolate missing samples;
- flags sample/sequence gaps, source-time gaps above 18 ms, non-monotonic
  source time, invalid samples, and the final partial window;
- stores an early run-completion message until all declared raw sequences have
  arrived, publishes the final window, and continues serving other runs;
- uses broker QoS inflight limiting, manual acknowledgement, and a bounded
  queue for backpressure; its Paho callback never waits for queue capacity and
  fails closed on an unexpected overflow;
- uses a stable client ID with `clean_session=false`, so a persistent broker
  queues QoS 1 raw/control messages during processor disconnections;
- commits exact input payloads to a synchronous SQLite journal before MQTT
  acknowledgement, replays active runs before readiness after restart, and
  prunes completed journals after QoS 1 feature publication;
- never finalizes an open window merely because the service is stopping; this
  prevents a restart from producing conflicting partial and complete windows;
- anchors windows to the first accepted source timestamp for each `run_id`, so
  replay speed and wall-clock delivery timing do not affect features.

Local Compose commands:

```sh
./tools/prepare_phase02_local.sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml up -d --wait \
  mqtt-broker signal-processor
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm \
  -e REPLAY_RATE=10 -e MAX_SAMPLES=1024 sensor-replay
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml down --remove-orphans
```

See `../../docs/phase-03-report.md` for exact tests and observed results.
Phase 03 is local-only; no VPS or Rahti deployment is included.
Phase 06 adds persistent-session plus journal recovery/readiness; it does not
alter source-time feature calculations or payload contracts.
