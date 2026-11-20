# RoadSense FastAPI

**Status: Phase 05 implemented and verified locally. No Rahti deployment exists.**

The read-only typed API exposes liveness/readiness, sessions, runs, features,
events, and aggregate status. Collection endpoints use bounded limit/offset
pagination. Queries are fixed, parameterized, and read-only; PostgreSQL remains
private. The local OpenAPI UI is `http://127.0.0.1:8000/docs` while the stack is
running.

Run its containerized unit suite with:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm --no-deps api-unit-tests
```

See `../../docs/contracts.md` and `../../docs/phase-05-report.md`.
