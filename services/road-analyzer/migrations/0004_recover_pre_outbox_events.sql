-- Migration 0002 initially marked pre-outbox events as published to avoid an
-- upgrade replay. That cannot distinguish a previously successful publish
-- from the old commit-before-publish failure window. Prefer at-least-once
-- recovery: deterministic event IDs make an extra historical delivery safe,
-- while leaving a committed event permanently unpublished is not recoverable.
UPDATE event_outbox
SET publish_attempts = 0,
    last_attempt_at = NULL,
    published_at = NULL
WHERE publish_attempts = 1
  AND last_error IS NULL
  AND last_attempt_at = created_at
  AND published_at = created_at;
