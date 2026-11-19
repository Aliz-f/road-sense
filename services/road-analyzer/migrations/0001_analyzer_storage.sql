CREATE TABLE sessions (
    session_id text PRIMARY KEY,
    sensor_id text NOT NULL,
    source_archive_sha256 character(64) NOT NULL,
    source_member text NOT NULL,
    source_start timestamptz NOT NULL,
    source_end timestamptz NOT NULL,
    row_count integer NOT NULL CHECK (row_count > 0),
    road_category text NOT NULL,
    orientation_note text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT sessions_source_bounds CHECK (source_end >= source_start),
    CONSTRAINT sessions_archive_hash_format CHECK (source_archive_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT sessions_source_revision_unique UNIQUE (source_archive_sha256, source_member)
);

CREATE TABLE runs (
    run_id uuid PRIMARY KEY,
    session_id text NOT NULL REFERENCES sessions(session_id),
    sensor_id text NOT NULL,
    algorithm_version text NOT NULL,
    replay_rate double precision,
    source_start timestamptz NOT NULL,
    source_end timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('observed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT runs_source_bounds CHECK (source_end > source_start),
    CONSTRAINT runs_replay_rate_positive CHECK (replay_rate IS NULL OR replay_rate > 0)
);

CREATE TABLE feature_windows (
    feature_window_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    window_index integer NOT NULL CHECK (window_index >= 0),
    algorithm_version text NOT NULL,
    source_start timestamptz NOT NULL,
    source_end timestamptz NOT NULL,
    sample_count integer NOT NULL CHECK (sample_count > 0),
    vibration_rms_mg double precision NOT NULL CHECK (vibration_rms_mg >= 0),
    peak_deviation_mg double precision NOT NULL CHECK (peak_deviation_mg >= 0),
    baseline_magnitude_mg double precision NOT NULL CHECK (baseline_magnitude_mg >= 0),
    baseline_method text NOT NULL CHECK (baseline_method = 'window_magnitude_median'),
    quality_flags text[] NOT NULL DEFAULT '{}',
    payload_sha256 character(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT feature_windows_one_second CHECK (source_end = source_start + interval '1 second'),
    CONSTRAINT feature_windows_payload_hash_format CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT feature_windows_idempotency UNIQUE (run_id, window_index, algorithm_version)
);

CREATE INDEX feature_windows_run_source_start_idx
    ON feature_windows (run_id, source_start);

CREATE TABLE events (
    event_id uuid PRIMARY KEY,
    feature_window_id bigint NOT NULL REFERENCES feature_windows(feature_window_id) ON DELETE CASCADE,
    run_id uuid NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    window_index integer NOT NULL CHECK (window_index >= 0),
    algorithm_version text NOT NULL,
    event_type text NOT NULL CHECK (event_type = 'high_vibration'),
    heuristic_type text NOT NULL CHECK (heuristic_type = 'vibration_rms_threshold'),
    rule_version text NOT NULL,
    severity text NOT NULL CHECK (severity = 'high'),
    threshold_vibration_rms_mg double precision NOT NULL CHECK (threshold_vibration_rms_mg > 0),
    observed_vibration_rms_mg double precision NOT NULL CHECK (observed_vibration_rms_mg >= threshold_vibration_rms_mg),
    payload_sha256 character(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT events_payload_hash_format CHECK (payload_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT events_idempotency UNIQUE (run_id, window_index, algorithm_version, rule_version),
    CONSTRAINT events_feature_rule_unique UNIQUE (feature_window_id, rule_version)
);

CREATE INDEX events_run_source_idx ON events (run_id, window_index);
