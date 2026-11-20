from __future__ import annotations

import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

import psycopg

from roadsense_api.config import ApiConfig
from roadsense_api.store import ApiStore


class StoreTests(unittest.TestCase):
    def config(self, directory: str) -> ApiConfig:
        current = Path(directory) / "password"
        previous = Path(directory) / "password.previous"
        current.write_text("old-password\n", encoding="utf-8")
        previous.write_text("future-password\n", encoding="utf-8")
        return ApiConfig("db", 5432, "roadsense", "reader", current, previous, 5)

    @patch("roadsense_api.store.psycopg.connect")
    def test_connection_falls_back_during_interrupted_rotation(self, connect):
        working = Mock()
        working.__enter__ = Mock(return_value=working)
        working.__exit__ = Mock(return_value=False)
        connect.side_effect = [psycopg.OperationalError("old rejected"), working]
        with tempfile.TemporaryDirectory() as directory:
            with ApiStore(self.config(directory)).connection() as connection:
                self.assertIs(connection, working)
        self.assertEqual(
            [call.kwargs["password"] for call in connect.call_args_list],
            ["old-password", "future-password"],
        )
        working.execute.assert_called_once_with("SET TRANSACTION READ ONLY")

    def test_runs_query_uses_independent_correlated_counts(self):
        executed: list[tuple[str, tuple[object, ...]]] = []
        count_cursor = Mock()
        count_cursor.fetchone.return_value = {"total": 1}
        page_cursor = Mock()
        page_cursor.fetchall.return_value = []
        connection = Mock()

        def execute(query, parameters=()):
            executed.append((query, tuple(parameters)))
            return count_cursor if query.startswith("SELECT count") else page_cursor

        connection.execute.side_effect = execute
        store = ApiStore.__new__(ApiStore)

        @contextmanager
        def fake_connection():
            yield connection

        store.connection = fake_connection
        items, total = store.runs("session-one", 25, 50)
        self.assertEqual(items, [])
        self.assertEqual(total, 1)
        page_query, parameters = executed[1]
        self.assertIn("SELECT count(*)::integer FROM feature_windows", page_query)
        self.assertIn("SELECT count(*)::integer FROM events", page_query)
        self.assertNotIn("LEFT JOIN feature_windows", page_query)
        self.assertNotIn("LEFT JOIN events", page_query)
        self.assertEqual(parameters, ("session-one", 25, 50))


if __name__ == "__main__":
    unittest.main()
