# RoadSense dashboard

**Status: Phase 05 implemented and verified locally.**

The Streamlit/Plotly dashboard selects recordings and runs, charts RMS and peak
deviation against source UTC time, overlays exploratory threshold events, and
shows processing status and immutable provenance. It calls FastAPI only; it has
no database or MQTT access. The local URL is `http://127.0.0.1:8501`.

Run its containerized smoke suite with:

```sh
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml run --rm --no-deps dashboard-smoke-tests
```

See `../../docs/phase-05-report.md`. In the Phase 06 distributed demo, this
same laptop container reaches private Rahti FastAPI through a loopback-only
`oc port-forward`; it is not deployed to Rahti or a VPS.
