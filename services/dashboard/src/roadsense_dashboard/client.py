from __future__ import annotations

from typing import Any
from uuid import UUID

import requests


class ApiClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}{path}", params=params, timeout=self.timeout_seconds
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("API response must be a JSON object")
        return payload

    def all_pages(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        request_params = dict(params or {})
        request_params.update({"limit": 500, "offset": 0})
        items: list[dict[str, Any]] = []
        while True:
            payload = self.get(path, request_params)
            page = payload.get("items")
            if not isinstance(page, list):
                raise ValueError("paginated API response is missing items")
            items.extend(page)
            total = payload.get("total")
            if not isinstance(total, int) or total < 0:
                raise ValueError("paginated API response has invalid total")
            if len(items) >= total or not page:
                return items
            request_params["offset"] = len(items)

    def sessions(self) -> list[dict[str, Any]]:
        return self.all_pages("/api/v1/sessions")

    def runs(self, session_id: str) -> list[dict[str, Any]]:
        return self.all_pages("/api/v1/runs", {"session_id": session_id})

    def features(self, run_id: UUID | str) -> list[dict[str, Any]]:
        return self.all_pages(f"/api/v1/runs/{run_id}/features")

    def events(self, run_id: UUID | str) -> list[dict[str, Any]]:
        return self.all_pages(f"/api/v1/runs/{run_id}/events")

    def status(self) -> dict[str, Any]:
        return self.get("/api/v1/status")
