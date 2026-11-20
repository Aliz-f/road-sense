from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = 2


@dataclass(frozen=True, slots=True)
class JournalRecord:
    record_id: int
    topic: str
    payload: bytes
    status: str
    run_id: str | None


class ProcessorState:
    """Durable input journal committed before an MQTT acknowledgement."""

    def __init__(self, path: Path, rejected_tombstone_limit: int = 1024) -> None:
        if rejected_tombstone_limit < 1:
            raise ValueError("rejected_tombstone_limit must be positive")
        self.path = path
        self.rejected_tombstone_limit = rejected_tombstone_limit
        self.connection = sqlite3.connect(path)
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _initialize(self) -> None:
        with self.connection:
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS processor_metadata (
                  key TEXT PRIMARY KEY,
                  value TEXT NOT NULL
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS input_journal (
                  record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  topic TEXT NOT NULL,
                  payload BLOB NOT NULL,
                  payload_sha256 TEXT NOT NULL,
                  run_id TEXT,
                  status TEXT NOT NULL CHECK (status IN ('pending','accepted','rejected')),
                  UNIQUE (topic, payload_sha256)
                )
                """
            )
            self.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rejected_tombstones (
                  tombstone_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  topic TEXT NOT NULL,
                  payload_sha256 TEXT NOT NULL,
                  UNIQUE (topic, payload_sha256)
                )
                """
            )
            row = self.connection.execute(
                "SELECT value FROM processor_metadata WHERE key='schema_version'"
            ).fetchone()
            if row is None:
                self.connection.execute(
                    "INSERT INTO processor_metadata (key,value) VALUES ('schema_version',?)",
                    (str(SCHEMA_VERSION),),
                )
            elif row[0] == "1":
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO rejected_tombstones (topic,payload_sha256)
                    SELECT topic,payload_sha256 FROM input_journal
                    WHERE status='rejected' ORDER BY record_id
                    """
                )
                self.connection.execute(
                    "DELETE FROM input_journal WHERE status='rejected'"
                )
                self.connection.execute(
                    "UPDATE processor_metadata SET value=? WHERE key='schema_version'",
                    (str(SCHEMA_VERSION),),
                )
            elif row[0] != str(SCHEMA_VERSION):
                raise ValueError("unsupported processor state schema version")
            self._trim_rejected_tombstones()

    def _trim_rejected_tombstones(self) -> None:
        self.connection.execute(
            """
            DELETE FROM rejected_tombstones
            WHERE tombstone_id NOT IN (
              SELECT tombstone_id FROM rejected_tombstones
              ORDER BY tombstone_id DESC LIMIT ?
            )
            """,
            (self.rejected_tombstone_limit,),
        )

    @staticmethod
    def _run_id(payload: bytes) -> str | None:
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(decoded, dict):
            return None
        value = decoded.get("run_id")
        return value if isinstance(value, str) and value else None

    def journal(self, topic: str, payload: bytes) -> JournalRecord:
        payload_hash = hashlib.sha256(payload).hexdigest()
        run_id = self._run_id(payload)
        tombstone = self.connection.execute(
            """
            SELECT tombstone_id FROM rejected_tombstones
            WHERE topic=? AND payload_sha256=?
            """,
            (topic, payload_hash),
        ).fetchone()
        if tombstone is not None:
            return JournalRecord(-tombstone[0], topic, payload, "rejected", run_id)
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO input_journal
                  (topic,payload,payload_sha256,run_id,status)
                VALUES (?,?,?,?, 'pending')
                ON CONFLICT (topic,payload_sha256) DO NOTHING
                """,
                (topic, payload, payload_hash, run_id),
            )
        row = self.connection.execute(
            """
            SELECT record_id,topic,payload,status,run_id
            FROM input_journal WHERE topic=? AND payload_sha256=?
            """,
            (topic, payload_hash),
        ).fetchone()
        if row is None or bytes(row[2]) != payload:
            raise RuntimeError("processor journal hash collision or missing record")
        return JournalRecord(row[0], row[1], bytes(row[2]), row[3], row[4])

    def recoverable(self) -> tuple[JournalRecord, ...]:
        rows = self.connection.execute(
            """
            SELECT record_id,topic,payload,status,run_id
            FROM input_journal
            WHERE status != 'rejected'
            ORDER BY record_id
            """
        ).fetchall()
        return tuple(
            JournalRecord(row[0], row[1], bytes(row[2]), row[3], row[4])
            for row in rows
        )

    def set_status(self, record_id: int, status: str) -> None:
        if status not in {"accepted", "rejected"}:
            raise ValueError("invalid processor journal status")
        with self.connection:
            if status == "rejected":
                row = self.connection.execute(
                    """
                    SELECT topic,payload_sha256 FROM input_journal
                    WHERE record_id=?
                    """,
                    (record_id,),
                ).fetchone()
                if row is None:
                    raise RuntimeError("processor journal record disappeared")
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO rejected_tombstones
                      (topic,payload_sha256) VALUES (?,?)
                    """,
                    row,
                )
                cursor = self.connection.execute(
                    "DELETE FROM input_journal WHERE record_id=?", (record_id,)
                )
                self._trim_rejected_tombstones()
            else:
                cursor = self.connection.execute(
                    "UPDATE input_journal SET status=? WHERE record_id=?",
                    (status, record_id),
                )
        if cursor.rowcount != 1:
            raise RuntimeError("processor journal record disappeared")

    def rejected_tombstone_count(self) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM rejected_tombstones"
        ).fetchone()
        if row is None:
            raise RuntimeError("processor rejected tombstone count failed")
        return row[0]

    def prune_completed(self, run_ids: set[str]) -> None:
        if not run_ids:
            return
        placeholders = ",".join("?" for _ in run_ids)
        with self.connection:
            self.connection.execute(
                f"DELETE FROM input_journal WHERE run_id IN ({placeholders}) AND status='accepted'",
                tuple(sorted(run_ids)),
            )

    def close(self) -> None:
        self.connection.close()
