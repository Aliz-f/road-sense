-- Reconstruct pre-outbox payloads in the exact canonical forms emitted by the
-- Python event builder: millisecond timestamps when exactly representable,
-- otherwise microseconds, and floating-point JSON values with a decimal point
-- when integral. This makes a recovery publish an exact duplicate of the
-- event whose canonical SHA-256 is stored in events.
WITH legacy_events AS (
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
           'source_start',
             CASE WHEN mod(extract(microseconds FROM f.source_start)::bigint, 1000) = 0
               THEN to_char(f.source_start AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
               ELSE to_char(f.source_start AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
             END,
           'source_end',
             CASE WHEN mod(extract(microseconds FROM f.source_end)::bigint, 1000) = 0
               THEN to_char(f.source_end AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
               ELSE to_char(f.source_end AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
             END,
           'algorithm_version', e.algorithm_version,
           'heuristic_type', e.heuristic_type,
           'rule_version', e.rule_version,
           'severity', e.severity,
           'threshold_vibration_rms_mg',
             CASE WHEN trunc(e.threshold_vibration_rms_mg) = e.threshold_vibration_rms_mg
               THEN (e.threshold_vibration_rms_mg::text || '.0')::numeric
               ELSE e.threshold_vibration_rms_mg::text::numeric
             END,
           'observed_vibration_rms_mg',
             CASE WHEN trunc(e.observed_vibration_rms_mg) = e.observed_vibration_rms_mg
               THEN (e.observed_vibration_rms_mg::text || '.0')::numeric
               ELSE e.observed_vibration_rms_mg::text::numeric
             END,
           'quality_flags', to_jsonb(f.quality_flags)
         ) AS payload
  FROM events e
  JOIN feature_windows f ON f.feature_window_id=e.feature_window_id
  JOIN runs r ON r.run_id=e.run_id
  JOIN sessions s ON s.session_id=r.session_id
  WHERE e.created_at < (
    SELECT applied_at FROM schema_migrations
    WHERE version='0002_reliability.sql'
  )
)
UPDATE event_outbox o
SET payload=legacy.payload,
    publish_attempts=0,
    last_attempt_at=NULL,
    last_error=NULL,
    published_at=NULL
FROM legacy_events legacy
WHERE o.event_id=legacy.event_id;
