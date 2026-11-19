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
whenever the threshold or rule semantics change. The result is not a pothole,
road-defect, or safety classification.

Migrations in `migrations/` are applied by the one-shot `analyzer-migrate`
Compose service before the analyzer starts. Runtime credentials come from the
ignored local environment file; no database or MQTT secret is stored here.

See `../../docs/contracts.md`, `../../docs/local-development.md`, and
`../../docs/phase-04-report.md` for the complete schema, event contract, and
verified commands.
