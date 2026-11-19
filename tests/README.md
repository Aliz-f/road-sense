# Tests

**Status: Phase 02 parser/schema/replay/reconnect and real-data MQTT tests are
implemented. Later-phase processing, persistence, API, and UI tests do not yet
exist.**

`phase02_e2e.sh` builds the Sensor Replay image, runs its unit suite, verifies
broker authentication, uses a separate schema-validating subscriber, and
replays actual private MUHOS data. Its cleanup trap removes only the
`roadsense-local` containers and network.

```sh
./tests/phase02_e2e.sh
PHASE02_FULL_REPLAY=true ./tests/phase02_e2e.sh
```

See `../docs/phase-02-report.md` and the numbered phase specifications.
