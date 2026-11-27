# Phase 06 deployment-plan correction report

Date: 2026-11-27
Branch: `chore/phase06-laptop-rahti`

## Scope and outcome

This repository-only correction removes the expiring personal VPS and public
Rahti endpoint assumptions from the active Phase 06 path. The complete local
Compose application remains unchanged. The distributed target is now laptop
Sensor Replay/Streamlit plus a private Rahti backend, connected through two
loopback-only authenticated `oc port-forward` sessions.

No VPS or Rahti system was accessed or modified. No image was published, no
public endpoint was created, and Phase 07 was not started.

The official course Final Project README was accessible on 2026-11-27. It says
the project should be dockerized, non-monolithic, use multiple communicating
microservices locally and with Rahti resources, and be submitted under the
course fork's `Final-Project/` with architecture and recorded demonstration
material. It does not state a VPS requirement. Course instructions remain
external and must be rechecked before submission.

## Implementation

- Added a small `rahti-client.compose.yaml` override that reuses the existing
  Sensor Replay and Streamlit services, resets local backend dependencies, and
  reaches laptop-loopback forwards through Linux host networking.
- Kept MQTT authentication and TLS verification. The private demo certificate
  generator now accepts `localhost` and issues both `localhost` and
  `mqtt-broker` DNS SANs.
- Removed the LoadBalancer-only broker node selector from the private core.
- Limited active render/apply/preflight/verify tooling to private Rahti stages.
  Archived Route, LoadBalancer and VPS files are visibly marked inactive.
- Limited image publishing to the four images actually deployed on Rahti;
  Sensor Replay and Streamlit remain locally built laptop images.
- Updated Phase 06, architecture, operations, submission, repository and
  infrastructure documentation. No data contracts, algorithms, migrations,
  API contracts, UI behavior or recovery code changed.

## Executed checks

Passed:

```sh
git diff --check
python3 -m unittest discover -s tests -p 'test_phase06_preparation.py' -v
for file in tools/phase06_*.sh; do bash -n "$file"; done
python3 -m py_compile tools/phase06_render_rahti.py tools/phase06_validate_secret_files.py
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml config --quiet
RAHTI_MQTT_USERNAME=roadsense-remote RAHTI_MQTT_PASSWORD=offline-placeholder \
  docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml \
  -f infrastructure/compose/rahti-client.compose.yaml config --quiet
python3 tools/phase06_render_rahti.py \
  --settings /tmp/roadsense-phase06-images.env \
  --output-dir /tmp/roadsense-phase06-rendered
```

The preparation suite passed 9 tests in its first run; after the final active
tooling assertion it passed 10 tests. Merged-Compose assertions confirmed both
clients use host networking, have no local backend dependency, target
`localhost:18883`/`localhost:18000`, and publish no Compose dashboard port
mapping in host mode; the override binds Streamlit itself to `127.0.0.1:8501`.
Render assertions confirmed exactly three manifests and
no Route, LoadBalancer, NodePort, LoadBalancer selector or unresolved variable.

Partially passed:

```sh
./tests/phase05_e2e.sh
```

The first sandboxed attempt could not access the local Docker socket. The
approved local-Docker rerun built the images, passed all 11 API tests and 6 of 7
dashboard tests, then stopped. The failing assertion required the dashboard's
methodology warning. A pre-existing, uncommitted user change in
`services/dashboard/src/roadsense_dashboard/app.py` comments out
`st.warning(LIMITATION)`. This correction neither changes nor stages that file.
The full cross-service portion therefore did not execute in this worktree.

Not verified:

- `kubectl create --dry-run=client --validate=false` still attempted discovery
  against the locally configured loopback API endpoint and failed; no server
  schema validation is claimed.
- Rahti server-side dry-run, SCC, storage, image pulls, NetworkPolicy behavior,
  migrations, port-forwards, TLS/authentication and restart/persistence need
  the real namespace and explicit deployment approval.

## Remaining Phase 06 gate

Verify actual immutable image digests and the OpenShift PostgreSQL image; obtain
approval; deploy in staged order; run one traceable laptop-to-Rahti replay; and
record sanitized run_id, TLS/authentication, persistence and recovery evidence.
Only then can Phase 06 be marked complete.
