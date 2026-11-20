# Tests

**Status: Phase 02 replay/MQTT, Phase 03 signal-processing, Phase 04
analyzer/PostgreSQL, and Phase 05 API/dashboard tests are implemented.**

`phase02_e2e.sh` builds the Sensor Replay image, runs its unit suite, verifies
broker authentication, uses a separate schema-validating subscriber, and
replays actual private MUHOS data. Its cleanup trap removes only the
`roadsense-local` containers and network.

```sh
./tests/phase02_e2e.sh
PHASE02_FULL_REPLAY=true ./tests/phase02_e2e.sh
```

See `../docs/phase-02-report.md` and the numbered phase specifications.

`phase03_e2e.sh` builds the independent processor, runs its network-disabled
unit suite, compares unpaced and 10× feature payloads against a separate
standard-library reference calculation, exercises broker backpressure with a
queue capacity of one, verifies completion without stopping the processor, and
optionally validates all 747 windows from the complete 62,169-row recording.

```sh
./tests/phase03_e2e.sh
PHASE03_FULL_REPLAY=true ./tests/phase03_e2e.sh
```

See `../docs/phase-03-report.md` for actual output and limitations.

`phase04_e2e.sh` runs the analyzer unit suite, interrupts and restores MQTT,
replays 1,536 actual Bumpy-gravel samples, independently checks all 19 stored
features and five threshold events, injects exact and conflicting duplicate
feature deliveries, and proves the named PostgreSQL volume survives container
recreation. Routine cleanup intentionally does not delete that volume.

```sh
./tests/phase04_e2e.sh
```

See `../docs/phase-04-report.md` for the threshold rationale, actual output,
and rollback procedure.

`phase05_e2e.sh` runs eleven API/config/store tests and seven dashboard
client/chart/UI tests, including successful Streamlit selection, statistics,
Plotly, and event rendering. It stages an interrupted PostgreSQL credential
rotation and proves API fallback/recovery, then starts the complete local
stack and replays 1,536 rows from each of two real recordings (Bumpy gravel and
Paved road 60kmh). It independently recomputes both sets of 19 feature
windows, checks their respective five and zero event results, renders each run
through the dashboard API client, verifies API-outage behavior and HTTP health,
and asserts that only the API and dashboard are loopback-published.

```sh
./tests/phase05_e2e.sh
```

See `../docs/phase-05-report.md` for actual output, startup commands, and
remaining limitations.

`test_phase06_preparation.py` is offline-only. It renders and structurally checks all
private Rahti manifests, checks immutable images and route inputs, verifies
credential byte consistency, persistent-session/security/PVC safeguards,
migration repeatability markers, VPS credential separation, and build-context
secret exclusions. It does not contact or validate a live Rahti project.

The Phase 03 end-to-end script also performs the Phase 06 recovery regression:
it kills the processor during a paced active replay after feature publication,
waits for journal recovery, and requires 19 exact, contiguous, deduplicated
windows from the original run. It retains processor state like the other named
development volumes and never uses `down --volumes`.
