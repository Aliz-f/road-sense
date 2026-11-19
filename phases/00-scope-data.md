# Phase 00 — Inspect MUHOS, confirm course scope, and prepare development decisions

**Status:** Completed on 2026-11-19 in branch `phase/00-scope-data`.
The reproducible evidence is in `docs/dataset-profile.md`,
`tools/inspect_muhos.py`, and `docs/assets/muhos-imu-summary.svg`. Phase 01 has
not started.

## Goal
Understand the real IMU/CAN data and confirm the local-laptop → VPS + Rahti development/deployment workflow is aligned with the official course submission requirements.

## Inputs
Official course Final-Project README; MUHOS archives already obtained by the student; local laptop access; user-provided prior inspection report, if available.

## Instructions
1. Read the latest official Final-Project README and record exactly what must be demonstrated and submitted.
2. Treat the **local laptop** as the complete Docker Compose development environment. The student's own VPS is an external production node, not a substitute for local development.
3. Inventory the actual Bosch IMU CSV files in the supplied bumpy-gravel, paved-road and highway archives; record original names, sizes, hashes, columns, units, timestamps, sample rates, missing records, sensor orientation uncertainty and license/attribution.
4. Examine CAN files for bumpy and paved sessions; document decoded SPEED signal, units to verify, time alignment and limitations.
5. Choose minimum recordings for MVP and write a dataset dictionary and reproducible summary/plots.
6. Review proposed MQTT message contract; note any field changes required based on actual file structure.
7. Review laptop storage and Docker prerequisites without installing or changing anything unless requested.

## Deliverables
`docs/dataset-profile.md`, source file provenance, data dictionary, source plots/inspection script when authorized, clear course submission checklist, verified/uncertain data fields.

## Exit checklist
- [x] Real filenames, units, timestamps, sampling summary and missing-data policy documented.
- [x] License and attribution recorded.
- [x] Full local Compose plan and later VPS/Rahti topology documented.
- [x] Course submission conditions checked without making unverified assertions.
- [x] No raw archives, tokens or credentials committed to public GitHub.

Validation command and result are recorded in `docs/dataset-profile.md`. The
inspector regenerated its JSON summary and byte-identical SVG; profile
assertions, SVG parsing, `git diff --check`, ignore checks, and the out-of-scope
service/infrastructure change check passed. Docker daemon connectivity remains
unverified because this session could not access its socket; no installation or
configuration change was attempted.

## Codex request
Implement **only Phase 00**, first reading AGENTS.md and the architecture/data-contract docs. Inspect the actual provided MUHOS archives on the laptop and document results. Do not deploy, create application microservices, or advance automatically.
