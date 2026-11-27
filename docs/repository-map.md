# Repository ownership

- `README.md`, `AGENTS.md`: project navigation and operational guardrails.
- `docs/`: architecture, contracts, operations, evidence and submission.
- `config/environments/`: secret-free inventories; real `.env` files are ignored.
- `phases/`: ordered specifications and acceptance criteria.
- `architecture/road-sense.mmd`: editable current laptop/Rahti diagram.
- `services/`: the seven application services developed in Phases 02–05.
- `infrastructure/compose/local.compose.yaml`: complete laptop application.
- `infrastructure/compose/rahti-client.compose.yaml`: laptop client override for
  private Rahti port-forwards.
- `infrastructure/rahti/`: active private OpenShift templates and runbook.
- `infrastructure/vps/`: inactive historical artifacts from the abandoned plan.
- `data/`: acquisition documentation and private mount guidance, not recordings.
- `tools/`: local validation, release, render and guarded deployment helpers.
- `tests/`: service, integration and offline Phase 06 preparation checks.

Sensor Replay and Streamlit remain laptop services in Phase 06. Mosquitto,
Signal Processor, Road Analyzer, PostgreSQL and FastAPI are deployed to Rahti
only after approval. No public endpoint manifest is in the active render/apply path.
