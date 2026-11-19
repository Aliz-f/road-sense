CREATE TABLE heuristic_rules (
    rule_version text PRIMARY KEY,
    heuristic_type text NOT NULL CHECK (heuristic_type = 'vibration_rms_threshold'),
    comparison_algorithm text NOT NULL CHECK (comparison_algorithm = 'vibration_rms_gte'),
    event_type text NOT NULL CHECK (event_type = 'high_vibration'),
    severity text NOT NULL CHECK (severity = 'high'),
    threshold_vibration_rms_mg double precision NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT heuristic_rules_version_format
      CHECK (rule_version ~ '^[a-z0-9][a-z0-9._-]{0,127}$'),
    CONSTRAINT heuristic_rules_threshold_finite_positive
      CHECK (threshold_vibration_rms_mg > 0
        AND threshold_vibration_rms_mg <> 'Infinity'::double precision
        AND threshold_vibration_rms_mg <> '-Infinity'::double precision
        AND threshold_vibration_rms_mg <> 'NaN'::double precision)
);

-- DISTINCT intentionally makes an already-reused rule version with different
-- thresholds fail this migration instead of choosing one silently.
INSERT INTO heuristic_rules (
  rule_version, heuristic_type, comparison_algorithm, event_type, severity,
  threshold_vibration_rms_mg
)
SELECT DISTINCT rule_version, heuristic_type, 'vibration_rms_gte', event_type,
                severity, threshold_vibration_rms_mg
FROM events;

ALTER TABLE events
  ADD CONSTRAINT events_rule_version_fk
  FOREIGN KEY (rule_version) REFERENCES heuristic_rules(rule_version);

CREATE TABLE event_outbox (
    event_id uuid PRIMARY KEY REFERENCES events(event_id) ON DELETE CASCADE,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    publish_attempts integer NOT NULL DEFAULT 0 CHECK (publish_attempts >= 0),
    last_attempt_at timestamptz,
    last_error text,
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT event_outbox_publish_state
      CHECK (published_at IS NULL OR last_error IS NULL)
);

-- Events created by migration 0001 predate outbox tracking and were published
-- by the old implementation before acknowledgement. Mark them complete so an
-- upgrade never emits historical events unexpectedly.
INSERT INTO event_outbox (event_id, payload, publish_attempts, last_attempt_at, published_at, created_at)
SELECT e.event_id,
       jsonb_build_object(
         'schema_version', 1,
         'event_id', e.event_id::text,
         'event_type', e.event_type,
         'run_id', e.run_id::text,
         'session_id', r.session_id,
         'sensor_id', r.sensor_id,
         'source_archive_sha256', s.source_archive_sha256,
         'source_member', s.source_member,
         'window_index', e.window_index,
         'source_start', to_char(f.source_start AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
         'source_end', to_char(f.source_end AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
         'algorithm_version', e.algorithm_version,
         'heuristic_type', e.heuristic_type,
         'rule_version', e.rule_version,
         'severity', e.severity,
         'threshold_vibration_rms_mg', e.threshold_vibration_rms_mg,
         'observed_vibration_rms_mg', e.observed_vibration_rms_mg,
         'quality_flags', to_jsonb(f.quality_flags)
       ),
       1, e.created_at, e.created_at, e.created_at
FROM events e
JOIN feature_windows f ON f.feature_window_id=e.feature_window_id
JOIN runs r ON r.run_id=e.run_id
JOIN sessions s ON s.session_id=r.session_id;

CREATE INDEX event_outbox_pending_idx
  ON event_outbox (created_at, event_id) WHERE published_at IS NULL;

ALTER TABLE sessions
  ADD CONSTRAINT sessions_identity_unique UNIQUE (session_id, sensor_id);

ALTER TABLE runs
  ADD CONSTRAINT runs_session_sensor_fk
  FOREIGN KEY (session_id, sensor_id)
  REFERENCES sessions(session_id, sensor_id);

ALTER TABLE feature_windows
  ADD CONSTRAINT feature_windows_identity_unique
  UNIQUE (feature_window_id, run_id, window_index, algorithm_version);

ALTER TABLE events
  ADD CONSTRAINT events_feature_identity_fk
  FOREIGN KEY (feature_window_id, run_id, window_index, algorithm_version)
  REFERENCES feature_windows(feature_window_id, run_id, window_index, algorithm_version);

ALTER TABLE runs
  ADD CONSTRAINT runs_replay_rate_finite
  CHECK (replay_rate IS NULL OR (
    replay_rate <> 'Infinity'::double precision
    AND replay_rate <> '-Infinity'::double precision
    AND replay_rate <> 'NaN'::double precision
  ));

ALTER TABLE feature_windows
  ADD CONSTRAINT feature_windows_metrics_finite CHECK (
    vibration_rms_mg <> 'Infinity'::double precision
    AND vibration_rms_mg <> '-Infinity'::double precision
    AND vibration_rms_mg <> 'NaN'::double precision
    AND peak_deviation_mg <> 'Infinity'::double precision
    AND peak_deviation_mg <> '-Infinity'::double precision
    AND peak_deviation_mg <> 'NaN'::double precision
    AND baseline_magnitude_mg <> 'Infinity'::double precision
    AND baseline_magnitude_mg <> '-Infinity'::double precision
    AND baseline_magnitude_mg <> 'NaN'::double precision
  );

ALTER TABLE events
  ADD CONSTRAINT events_metrics_finite CHECK (
    threshold_vibration_rms_mg <> 'Infinity'::double precision
    AND threshold_vibration_rms_mg <> '-Infinity'::double precision
    AND threshold_vibration_rms_mg <> 'NaN'::double precision
    AND observed_vibration_rms_mg <> 'Infinity'::double precision
    AND observed_vibration_rms_mg <> '-Infinity'::double precision
    AND observed_vibration_rms_mg <> 'NaN'::double precision
  );
