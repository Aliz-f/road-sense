from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from .model import Feature, SessionRecord
from .schema import SHA256_PATTERN, parse_timestamp


class SessionRegistry:
    def __init__(self, sessions: dict[str, SessionRecord]) -> None:
        self.sessions = sessions

    @classmethod
    def load(cls, path: Path) -> "SessionRegistry":
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, list) or not raw:
            raise ValueError("session registry must be a non-empty array")
        sessions: dict[str, SessionRecord] = {}
        expected_fields = {
            "session_id", "sensor_id", "source_archive_sha256", "source_member",
            "source_start", "source_end", "row_count", "road_category", "orientation_note",
        }
        for item in raw:
            if not isinstance(item, dict) or set(item) != expected_fields:
                raise ValueError("session registry entry fields are invalid")
            strings = {}
            for field in expected_fields - {"row_count", "source_start", "source_end"}:
                value = item[field]
                if not isinstance(value, str) or not value:
                    raise ValueError(f"session registry {field} must be non-empty")
                strings[field] = value
            if not SHA256_PATTERN.fullmatch(strings["source_archive_sha256"]):
                raise ValueError("session registry archive hash must be lowercase SHA-256")
            row_count = item["row_count"]
            if not isinstance(row_count, int) or isinstance(row_count, bool) or row_count <= 0:
                raise ValueError("session registry row_count must be positive")
            start_text, start = parse_timestamp(item["source_start"], "source_start")
            end_text, end = parse_timestamp(item["source_end"], "source_end")
            if end < start:
                raise ValueError("session registry source bounds are inverted")
            session = SessionRecord(
                session_id=strings["session_id"], sensor_id=strings["sensor_id"],
                source_archive_sha256=strings["source_archive_sha256"],
                source_member=strings["source_member"], source_start=start, source_end=end,
                source_start_text=start_text, source_end_text=end_text, row_count=row_count,
                road_category=strings["road_category"], orientation_note=strings["orientation_note"],
            )
            if session.session_id in sessions:
                raise ValueError(f"duplicate session registry ID: {session.session_id}")
            sessions[session.session_id] = session
        return cls(sessions)

    def match(self, feature: Feature) -> SessionRecord:
        try:
            session = self.sessions[feature.session_id]
        except KeyError as error:
            raise ValueError(f"unknown session_id: {feature.session_id}") from error
        actual = (feature.sensor_id, feature.source_archive_sha256, feature.source_member)
        expected = (session.sensor_id, session.source_archive_sha256, session.source_member)
        if actual != expected:
            raise ValueError("feature provenance conflicts with the session registry")
        expected_start = session.source_start + timedelta(seconds=feature.window_index)
        if feature.source_start != expected_start:
            raise ValueError("feature source_start does not match session anchor/window_index")
        if feature.source_start > session.source_end:
            raise ValueError("feature window begins after the recorded session")
        return session
