from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from signal_processor.state import ProcessorState


class ProcessorStateTests(unittest.TestCase):
    def test_journal_survives_reopen_and_deduplicates_exact_delivery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.sqlite3"
            payload = json.dumps({"run_id": "run-1", "value": 1}).encode()
            state = ProcessorState(path)
            first = state.journal("raw", payload)
            state.set_status(first.record_id, "accepted")
            state.close()

            reopened = ProcessorState(path)
            duplicate = reopened.journal("raw", payload)
            self.assertEqual(duplicate.record_id, first.record_id)
            self.assertEqual(duplicate.status, "accepted")
            self.assertEqual(len(reopened.recoverable()), 1)
            reopened.close()

    def test_rejected_records_are_not_recovered_and_completed_runs_prune(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            state = ProcessorState(Path(temp) / "state.sqlite3")
            rejected = state.journal("raw", b"not-json")
            state.set_status(rejected.record_id, "rejected")
            accepted = state.journal("raw", b'{"run_id":"run-2"}')
            state.set_status(accepted.record_id, "accepted")
            self.assertEqual([item.record_id for item in state.recoverable()], [accepted.record_id])
            state.prune_completed({"run-2"})
            self.assertEqual(state.recoverable(), ())
            state.close()

    def test_rejected_tombstones_are_bounded_without_pruning_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.sqlite3"
            state = ProcessorState(path, rejected_tombstone_limit=2)
            accepted = state.journal("raw", b'{"run_id":"active-run"}')
            state.set_status(accepted.record_id, "accepted")
            rejected_payloads = [b"invalid-0", b"invalid-1", b"invalid-2"]
            for payload in rejected_payloads:
                record = state.journal("raw", payload)
                state.set_status(record.record_id, "rejected")

            self.assertEqual(state.rejected_tombstone_count(), 2)
            duplicate = state.journal("raw", rejected_payloads[-1])
            self.assertEqual(duplicate.status, "rejected")
            self.assertLess(duplicate.record_id, 0)
            expired = state.journal("raw", rejected_payloads[0])
            self.assertEqual(expired.status, "pending")
            state.set_status(expired.record_id, "rejected")
            self.assertEqual(state.rejected_tombstone_count(), 2)
            self.assertEqual(
                [item.record_id for item in state.recoverable()],
                [accepted.record_id],
            )
            rejected_rows = state.connection.execute(
                "SELECT COUNT(*) FROM input_journal WHERE status='rejected'"
            ).fetchone()
            self.assertEqual(rejected_rows, (0,))
            state.close()

            reopened = ProcessorState(path, rejected_tombstone_limit=2)
            self.assertEqual(
                reopened.journal("raw", rejected_payloads[-1]).status,
                "rejected",
            )
            self.assertEqual(
                [item.record_id for item in reopened.recoverable()],
                [accepted.record_id],
            )
            reopened.close()

    def test_version_one_rejected_rows_migrate_to_bounded_tombstones(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "state.sqlite3"
            connection = sqlite3.connect(path)
            connection.executescript(
                """
                CREATE TABLE processor_metadata (
                  key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                INSERT INTO processor_metadata VALUES ('schema_version','1');
                CREATE TABLE input_journal (
                  record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  topic TEXT NOT NULL,
                  payload BLOB NOT NULL,
                  payload_sha256 TEXT NOT NULL,
                  run_id TEXT,
                  status TEXT NOT NULL CHECK (status IN ('pending','accepted','rejected')),
                  UNIQUE (topic, payload_sha256)
                );
                """
            )
            payload = b"legacy-invalid"
            accepted_payload = b'{"run_id":"legacy-active"}'
            connection.execute(
                """
                INSERT INTO input_journal
                  (topic,payload,payload_sha256,run_id,status)
                VALUES (?,?,?,?, 'rejected')
                """,
                ("raw", payload, hashlib.sha256(payload).hexdigest(), None),
            )
            connection.execute(
                """
                INSERT INTO input_journal
                  (topic,payload,payload_sha256,run_id,status)
                VALUES (?,?,?,?, 'accepted')
                """,
                (
                    "raw",
                    accepted_payload,
                    hashlib.sha256(accepted_payload).hexdigest(),
                    "legacy-active",
                ),
            )
            connection.commit()
            connection.close()

            state = ProcessorState(path, rejected_tombstone_limit=2)
            self.assertEqual(state.journal("raw", payload).status, "rejected")
            self.assertEqual(state.rejected_tombstone_count(), 1)
            self.assertEqual(
                [item.payload for item in state.recoverable()],
                [accepted_payload],
            )
            version = state.connection.execute(
                "SELECT value FROM processor_metadata WHERE key='schema_version'"
            ).fetchone()
            self.assertEqual(version, ("2",))
            state.close()


if __name__ == "__main__":
    unittest.main()
