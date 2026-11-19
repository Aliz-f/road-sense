# Tests

**Status: Phase 02 replay/MQTT, Phase 03 signal-processing, and Phase 04
analyzer/PostgreSQL tests are implemented. API and UI tests do not yet exist.**

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
