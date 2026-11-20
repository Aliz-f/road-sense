from __future__ import annotations

import json
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


if __name__ == "__main__":
    unittest.main()
