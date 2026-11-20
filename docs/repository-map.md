# Repository ownership

README.md: project navigation and objective.
AGENTS.md: Codex operational guardrails.
docs/: design decisions, architecture, contracts, operations and submission.
config/environments/: secret-free environment templates; actual `.env` files are private and ignored.
phases/: eight ordered implementation specifications and acceptance criteria.
architecture/road-sense.mmd: editable conceptual diagram.
services/sensor-replay/: local MUHOS-to-MQTT replay implementation, Phase 02; later deployed to VPS in Phase 06.
services/signal-processor/: local source-time window feature calculation, Phase 03; later deployed to Rahti in Phase 06.
services/road-analyzer/: local Phase 04 rules, migrations, event publication,
and PostgreSQL persistence; later deployed to Rahti in Phase 06.
services/api/: read-only typed FastAPI service developed locally in Phase 05;
later deployed to Rahti in Phase 06.
services/dashboard/: Streamlit/Plotly API client developed locally in Phase 05;
later deployed to VPS in Phase 06.
infrastructure/vps/: private VPS deployment/runbook, Phase 06.
infrastructure/compose/: Phase 01 preflight, complete laptop development stack (Phases 02–05), and VPS runtime stack (Phase 06).
infrastructure/rahti/: Kubernetes manifests/runbooks, Phase 06.
data/: documented acquisition and private data mounts, Phase 00.
tools/: dataset inspection, local validation, and ignored local credential/TLS preparation utilities.
tests/: Phase 02 MQTT tests and Phase 03 cross-service feature integration/reference checks.

API and dashboard containers, tests, and the complete local Compose path are
implemented. No Phase 06 Kubernetes/VPS manifest or cloud deployment is part
of the current scope.
