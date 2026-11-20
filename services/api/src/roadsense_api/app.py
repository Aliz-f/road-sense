from __future__ import annotations

from typing import Annotated, Any, TypeVar
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from psycopg import Error as PostgresError
from pydantic import BaseModel

from .config import ApiConfig
from .models import (
    EventResponse, FeatureResponse, HealthResponse, Page, RunResponse,
    SessionResponse, StatusResponse,
)
from .store import ApiStore

app = FastAPI(
    title="RoadSense API",
    version="1.0.0",
    description="Read-only exploratory vehicle-vibration observations; not a pothole or safety API.",
)


@app.exception_handler(PostgresError)
async def postgres_unavailable(_request: Request, _error: PostgresError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": "database unavailable"})


def get_store() -> ApiStore:
    return ApiStore(ApiConfig.from_env())


Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]
ModelT = TypeVar("ModelT", bound=BaseModel)


def response_page(model: type[ModelT], rows: list[dict[str, Any]], total: int, limit: int, offset: int) -> dict[str, Any]:
    items = [model.model_validate(row) for row in rows]
    return {"items": items, "limit": limit, "offset": offset, "count": len(items), "total": total}


@app.get("/health/live", response_model=HealthResponse)
def live() -> HealthResponse:
    return HealthResponse(status="live")


@app.get("/health/ready", response_model=HealthResponse)
def ready(store: Annotated[ApiStore, Depends(get_store)]) -> HealthResponse:
    try:
        store.ready()
    except (OSError, ValueError, PostgresError) as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable") from error
    return HealthResponse(status="ready")


@app.get("/api/v1/sessions", response_model=Page[SessionResponse])
def sessions(store: Annotated[ApiStore, Depends(get_store)], limit: Limit = 100, offset: Offset = 0):
    rows, total = store.sessions(limit, offset)
    return response_page(SessionResponse, rows, total, limit, offset)


@app.get("/api/v1/runs", response_model=Page[RunResponse])
def runs(store: Annotated[ApiStore, Depends(get_store)], limit: Limit = 100, offset: Offset = 0, session_id: str | None = None):
    rows, total = store.runs(session_id, limit, offset)
    return response_page(RunResponse, rows, total, limit, offset)


def ensure_run(store: ApiStore, run_id: UUID) -> None:
    if not store.run_exists(run_id):
        raise HTTPException(status_code=404, detail="run not found")


@app.get("/api/v1/runs/{run_id}/features", response_model=Page[FeatureResponse])
def features(run_id: UUID, store: Annotated[ApiStore, Depends(get_store)], limit: Limit = 500, offset: Offset = 0):
    ensure_run(store, run_id)
    rows, total = store.features(run_id, limit, offset)
    return response_page(FeatureResponse, rows, total, limit, offset)


@app.get("/api/v1/runs/{run_id}/events", response_model=Page[EventResponse])
def events(run_id: UUID, store: Annotated[ApiStore, Depends(get_store)], limit: Limit = 500, offset: Offset = 0):
    ensure_run(store, run_id)
    rows, total = store.events(run_id, limit, offset)
    return response_page(EventResponse, rows, total, limit, offset)


@app.get("/api/v1/status", response_model=StatusResponse)
def api_status(store: Annotated[ApiStore, Depends(get_store)]) -> StatusResponse:
    return StatusResponse.model_validate(store.status())
