# Repository ownership

README.md: project navigation and objective.
AGENTS.md: Codex operational guardrails.
docs/: design decisions, architecture, contracts, operations and submission.
phases/: eight ordered implementation specifications and acceptance criteria.
architecture/road-sense.mmd: editable conceptual diagram.
services/sensor-replay/: developed on laptop in Phase 02; later deployed to VPS in Phase 06.
services/signal-processor/: Rahti window feature calculation, Phase 03.
services/road-analyzer/: Rahti rules + persistence, Phase 04.
services/api/: Rahti HTTP API, Phase 05.
services/dashboard/: developed on laptop in Phase 05; later deployed to VPS in Phase 06.
infrastructure/vps/: private VPS deployment/runbook, Phase 06.
infrastructure/compose/: complete laptop development stack (Phases 02–05) and VPS runtime stack (Phase 06).
infrastructure/rahti/: Kubernetes manifests/runbooks, Phase 06.
data/: documented acquisition and private data mounts, Phase 00.
tests/: tests created during future implementation phases.

All empty directories contain README files for documentation-only placeholders. No Dockerfiles, Python application scripts, Kubernetes manifests or cloud deployments are part of the current scope.
