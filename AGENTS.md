# Codex instructions — RoadSense

STATUS: Phases 00–05 are implemented and tested locally. Phase 06 deployment
preparation is completed and merged, but actual VPS and CSC Rahti deployment is
pending. Phase 07 has not started.

1. Read README.md, docs/architecture.md, docs/contracts.md, docs/operations.md, and the selected phases file.
2. Execute ONE phase at a time. Do not proceed until that phase's acceptance checks pass.
3. Check actual MUHOS files, official course instructions and Rahti limitations; never invent observed data, units, timestamps, or test outcomes.
4. Work in a phase-specific branch/PR. Avoid modifying unrelated services.
5. For implementations: add tests, exact run commands, sanitized logs and an implementation report.
6. Require approval before installing local or VPS packages, changing SSH/firewall/DNS, spending money, exposing public services, or deploying to Rahti.
7. No secrets, private files or raw dataset archives in Git. Pin image versions, authenticate MQTT, use TLS, keep DB internal.
8. Use run_id/sequence_id for traceability; design for duplicate MQTT messages and service restart.
9. Project measures exploratory vehicle vibrations, NOT scientifically validated potholes or safety classifications.
10. Stop after completing the chosen phase; report blockers and unmet checks without claiming success.

**Mandatory workflow:** Phases 00–05 run and are tested entirely on the user's **local laptop** using Docker Compose. Only Phase 06 deploys services to the personally owned **VPS** and **CSC Rahti**; do not touch either remote environment earlier. The GitHub repo is the development source; verify separate GitLab submission requirements.
