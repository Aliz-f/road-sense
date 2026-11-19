# Road Analyzer

The Phase 04 Road Analyzer is an independent Python service. It subscribes to
QoS 1 feature messages on `roadsense/v1/imu/features`, validates the complete
v1 contract, writes immutable/idempotent records to PostgreSQL, and publishes
exploratory high-vibration events on `roadsense/v1/events`.

The default rule is:

```text
vibration_rms_mg >= 100.0
```

`ANALYZER_VIBRATION_RMS_THRESHOLD_MG` configures the numeric threshold and
`ANALYZER_RULE_VERSION` identifies that configuration. Change the rule version
whenever the threshold or rule semantics change. PostgreSQL rejects an
incompatible reuse of an existing rule version. The result is not a pothole,
road-defect, or safety classification.

Migrations in `migrations/` are applied by the one-shot `analyzer-migrate`
Compose service before the analyzer starts. The ignored stable password file
is rotated explicitly with `tools/rotate_phase04_postgres_password.sh --apply`;
no database or MQTT secret is stored here.

Events and outbox rows commit atomically. Pending rows are retried at startup
and while running, and publication completes only after MQTT QoS 1
acknowledgement. Delivery is at least once, so consumers deduplicate by the
deterministic event UUID. The analyzer reconnects and retries idempotent
database operations after temporary PostgreSQL outages.

See `../../docs/contracts.md`, `../../docs/local-development.md`, and
`../../docs/phase-04-report.md` for the complete schema, event contract, and
verified commands.
