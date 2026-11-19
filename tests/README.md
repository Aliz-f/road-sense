# Tests

**Status: Phase 02 replay/MQTT and Phase 03 signal-processing tests are
implemented. Persistence, API, and UI tests do not yet exist.**

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
