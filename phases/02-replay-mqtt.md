# Phase 02 — Local Sensor Feeder + MQTT

**Status:** Not started. Documentation only.

## Goal
Run the first sensor-streaming pipeline **entirely on the laptop** using Docker Compose.

## Inputs
Phase 00 verified Bosch IMU data; Phase 01 laptop Docker setup; docs/contracts.md.

## Instructions
1. Implement independent Python feeder to parse recorded IMU CSVs into bounded MQTT batches preserving source timestamps.
2. Add recording/session metadata, unique run_id, sequence and sample_index, configurable replay rate, graceful shutdown and structured logs.
3. Dockerize feeder and run Mosquitto as a second service **in local Docker Compose**. Use development authentication and internal network.
4. Publish `roadsense/v1/imu/raw`; verify with a separate local test subscriber.
5. Add parser, schema, timestamp and reconnect tests.
6. Document local run/stop and sample output, avoiding secrets and raw dataset commits.

## Deliverables
`services/sensor-replay` code/Dockerfile and tests; local broker configuration and Compose; tested MQTT samples and developer runbook.

## Exit checklist
- [ ] Actual IMU CSV successfully replayed from laptop.
- [ ] Local broker accepts authenticated messages and local subscriber receives them.
- [ ] Source time, run_id, sequence preserved and playback adjustable.
- [ ] No publicly exposed broker or credentials in Git.
- [ ] No services deployed remotely.

## Codex request
Implement **only Phase 02** using local laptop Docker Compose. Do not use the VPS or Rahti. Provide runnable test evidence, then stop.
