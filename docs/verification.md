# Validation, troubleshooting and demonstration checklist

## 1. Confirm application health

**Fully local:**

```bash
docker compose --env-file config/environments/local/.env.runtime \
  -f infrastructure/compose/local.yaml ps -a
curl -fsS http://127.0.0.1:8000/health/ready
curl -fsS http://127.0.0.1:8501/_stcore/health
```

**Rahti:**

```bash
export RAHTI_NAMESPACE="$(oc project -q)"
./tools/verify_rahti.sh rahti
oc -n "$RAHTI_NAMESPACE" get pvc
curl -fsS http://127.0.0.1:18000/health/ready
curl -fsS http://127.0.0.1:8501/_stcore/health
```

The Rahti HTTP checks require both port-forwards to be running. `1/1 Running` demonstrates successful scheduling and readiness, but **not** a complete end-to-end data trace.

## 2. Confirm the full replay pipeline

- Make sure `Bumpy Gravel - imu.tar` exists at the private dataset path and matches the configured SHA-256.
- Start the broker, processor, analyzer, database, API and dashboard in the selected mode.
- Generate and record a new `RUN_ID`.
- Replay 1,536 samples with `MAX_SAMPLES=1536`, `REPLAY_RATE=0` and `BATCH_SIZE=64`.
- Query the `/features` and `/events` endpoints for that run ID.
- Confirm the same run is visible in Streamlit. The known local reference was 19 feature windows and 5 events for the Bumpy Gravel recording.
- Verify that replaying a different UUID yields a distinct run and doesn't duplicate existing records.
- Record logs and screenshots without passwords, access tokens or private dataset rows.

## 3. Troubleshooting table

| Symptom | First check | Likely action |
|---|---|---|
| Local Compose cannot find archive | `ROADSENSE_DATASET_ROOT` and file checksum | Correct path; don't disable SHA check |
| API returns connection refused | `docker compose ps`, `oc port-forward` status | Restart only affected component/tunnel |
| Streamlit healthy but browser cannot connect on Linux Docker Desktop | `docker context show`; `curl localhost:8501/_stcore/health` | Enable Docker Desktop host networking and recreate laptop container |
| Rahti `FailedCreate` | `oc describe deployment` / sorted events | Check minimum CPU, quotas, SCC |
| Rahti `ErrImagePull` / `unauthorized` | Pod events and GHCR package visibility | Give Rahti registry pull permission |
| Rahti `CrashLoopBackOff` | `oc logs deployment/NAME --previous` | Inspect application error or wrong test-stage image |
| Rahti PVC `Pending` | `oc describe pvc NAME` | Inspect `WaitForFirstConsumer` or quota/storage |
| MQTT TLS certificate error | `openssl s_client` with correct CA file | Use original matching CA and certificate; do not disable verification |
| Dashboard loads but no events | API `/status`, run `/features`, analyzer logs | Check source, threshold and run ID |

Never troubleshoot by deleting credentials or persistent volumes without first identifying the cause.

## 4. Suggested demonstration (~10 minutes)

1. Introduce the IMU dataset and the high-vibration objective.
2. Explain the pipeline with the architecture diagram.
3. Show the code structure, Dockerfiles and two deployment modes.
4. Demonstrate the healthy Rahti (or fully local) services, storage and private networking.
5. Replay a small MUHOS session and show the emitted run UUID.
6. Read `/features` and `/events` for that run, then show the corresponding Streamlit charts.
7. Explain TLS authentication, duplicate processing, durable storage and recovery limitations.
8. Conclude with the exploratory nature of the vibration threshold and next steps.

Check the latest University of Oulu course submission instructions before recording. Submit through the required course GitLab location and include an architecture image and demonstration video link if requested.

## 5. Secret and release hygiene

Never commit `data/raw`, the MUHOS tar files, `.env.runtime`, `rahti-client.env`, `images.env`, generated manifests, private CA keys or passwords. Keep the old image digests before each new Rahti rollout and back up state before disruptive tests.
