ALTER TABLE runs
  ADD CONSTRAINT runs_algorithm_identity_unique UNIQUE (run_id, algorithm_version);

ALTER TABLE feature_windows
  ADD CONSTRAINT feature_windows_run_algorithm_fk
  FOREIGN KEY (run_id, algorithm_version)
  REFERENCES runs(run_id, algorithm_version);

ALTER TABLE heuristic_rules
  ADD CONSTRAINT heuristic_rules_event_identity_unique
  UNIQUE (rule_version, heuristic_type, event_type, severity, threshold_vibration_rms_mg);

ALTER TABLE events
  ADD CONSTRAINT events_rule_configuration_fk
  FOREIGN KEY (
    rule_version, heuristic_type, event_type, severity, threshold_vibration_rms_mg
  ) REFERENCES heuristic_rules (
    rule_version, heuristic_type, event_type, severity, threshold_vibration_rms_mg
  );

ALTER TABLE feature_windows
  ADD CONSTRAINT feature_windows_observation_identity_unique
  UNIQUE (
    feature_window_id, run_id, window_index, algorithm_version, vibration_rms_mg
  );

ALTER TABLE events
  ADD CONSTRAINT events_observation_fk
  FOREIGN KEY (
    feature_window_id, run_id, window_index, algorithm_version,
    observed_vibration_rms_mg
  ) REFERENCES feature_windows (
    feature_window_id, run_id, window_index, algorithm_version, vibration_rms_mg
  );
