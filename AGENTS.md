# Codex instructions — RoadSense

STATUS: Phases 00–05 are implemented and tested locally. Phase 06 repository
preparation targets the local Linux laptop plus CSC Rahti only; no Rahti
deployment has been performed. Phase 07 has not started.

1. Read README.md, docs/architecture.md, docs/contracts.md, docs/operations.md, and the selected phase file.
2. Execute one phase at a time; do not proceed until its acceptance checks pass.
3. Check actual MUHOS files, official course instructions and Rahti limitations; never invent observed data, units, timestamps, or outcomes.
4. Work in a phase-specific branch/PR and avoid unrelated services.
5. For implementations, add tests, exact commands, sanitized logs and an implementation report.
6. Require approval before installing packages, changing SSH/firewall/DNS, spending money, exposing public services, publishing images, or deploying to Rahti.
7. Never commit secrets, private files or raw dataset archives. Pin deployed images, authenticate MQTT, verify TLS and keep PostgreSQL internal.
8. Preserve run_id/sequence_id traceability, duplicate handling and restart recovery.
9. Describe only exploratory vehicle-vibration measurements, not scientifically validated potholes or safety classifications.
10. Stop after the chosen phase; report blockers and unmet live checks without claiming deployment success.

**Mandatory workflow:** Phases 00–05 run entirely on the laptop with Docker
Compose. Phase 06 keeps that local application and deploys only Mosquitto,
Signal Processor, Road Analyzer, PostgreSQL and FastAPI to the existing CSC
Rahti OpenShift environment. The laptop may run Sensor Replay and Streamlit for
a cross-environment demo through loopback-only `oc port-forward`. Do not use a
VPS, create public endpoints, install another Kubernetes distribution, or touch
remote infrastructure without explicit approval. GitHub is the development
source; separately satisfy the official GitLab `Final-Project/` submission.
