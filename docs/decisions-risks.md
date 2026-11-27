# Decisions, assumptions and risks

## Confirmed plan

- The Linux laptop runs the complete application locally with Docker Compose.
- CSC Rahti runs Mosquitto, Signal Processor, Road Analyzer, PostgreSQL/PVC and FastAPI.
- Laptop Sensor Replay and Streamlit use loopback-only `oc port-forward` for a distributed demo.
- No VPS, public API Route, public MQTT LoadBalancer, external DNS or second Kubernetes cluster.
- Algorithms and outputs remain exploratory vibration metrics.

## Live checks still needed

1. Rahti quota, SCC/seccomp, arbitrary UID, storage class and NetworkPolicy behavior.
2. Registry pulls and immutable image/platform compatibility.
3. OpenShift PostgreSQL image startup, migration and PVC ownership/path.
4. Service port-forward behavior for MQTT and API on the actual project.
5. Broker, database and processor journal persistence/recovery.
6. Exact GitLab course-fork submission contents and current demo rules.

## Risks and responses

- **Port-forward interrupted:** keep commands foregrounded, demonstrate reconnect,
  and treat the tunnel as temporary demo access rather than availability design.
- **TLS name mismatch:** issue the private broker certificate with both
  `localhost` and `mqtt-broker` DNS SANs; never disable verification.
- **Misleading results:** retain units/provenance and avoid pothole/safety claims.
- **Duplicates/restarts:** preserve QoS 1, stable client IDs, idempotency keys,
  analyzer outbox and processor journal PVC.
- **Data loss:** verify backups, then perform controlled restart tests; never
  delete PVCs as rollback.
- **Course mismatch:** cite the official instructions and recheck them before submission.

The personal VPS/public-endpoint plan is abandoned historical context, not a
fallback that should be deployed without a new scoped decision and approval.
