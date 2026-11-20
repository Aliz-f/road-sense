# Phase 06 deployment-preparation correction report

Date: 2026-11-20 (Europe/Helsinki)

## Scope and outcome

This branch corrects deployment preparation only. No VPS or Rahti resource was
accessed or changed, no image was published, no endpoint was exposed, and no
remote deployment success is claimed. Phase 06 exit checks remain open.

The correction preserves the Phase 05 payload/database/API behavior and adds:

- newline-free PostgreSQL Secret bytes plus a non-disclosing credential-file
  validator and regression checks for the environment/file consumers;
- a stable MQTT 3.1.1 Signal Processor client identity with
  `clean_session=false`, disconnect-aware readiness, and regression tests;
- Rahti's current explicit `Localhost/rahti-custom-seccomp.json` profile and
  resource request/limit ratios no greater than five;
- a fresh generate-name migration Job per execution, database advisory
  locking/checksums, a release-derived migration ID, and an apps-stage success
  marker gate;
- separate VPS Compose interpolation, dashboard, and Sensor Replay files so
  MQTT credentials are not injected into Streamlit;
- an init-container write/remove check for Mosquitto's PVC under the assigned
  UID/fsGroup model;
- rendered manifest structure tests, stricter CIDR validation, server-side dry-run gates,
  processor/PostgreSQL readiness checks, and broader Docker context exclusions.

The seccomp and UID/fsGroup choices were checked against the current
[CSC workload security documentation](https://docs.csc.fi/cloud/rahti/configurations/workload-security/).
The PVC assumptions were checked against
[CSC persistent storage documentation](https://docs.csc.fi/cloud/rahti/usage/storage/persistent/).
These documents describe policy; only the actual project can prove admission,
storage permissions, and runtime behavior.

## Offline verification performed

Commands were run from the Phase 06 worktree. Outputs below are summarized and
contain no credentials.

```sh
python3 -m unittest discover -s tests -p 'test_phase06_preparation.py' -v
```

Result: PASS, 9 tests. This rendered and structurally checked private manifests and checked
immutable images, route/CIDR inputs, Secret byte consistency, Rahti seccomp and
Mosquitto PVC safeguards, migration identifiers, VPS configuration separation,
and Docker build-context exclusions.

```sh
docker create ... roadsense/signal-processor-test:phase03-local ...
docker cp services/signal-processor/{src,tests} ...
docker start -a roadsense-phase06-processor-unit
```

Result: PASS, 27 tests in a cached test image with networking disabled. This
includes persistent-session construction, resubscription, readiness cleanup,
client-ID validation, source-time processing, duplicate handling, completion,
gap and schema behavior. The disposable container was removed afterward.

```sh
for file in tools/phase06_*.sh; do bash -n "$file"; done
python3 -m py_compile tools/phase06_render_rahti.py \
  tools/phase06_validate_secret_files.py \
  services/signal-processor/src/signal_processor/{config,mqtt_service,health}.py
git diff --check
```

Result: PASS.

```sh
docker compose --env-file .env -f compose.yaml config --quiet
```

Result: PASS against temporary copies of all three VPS example environment
files. No service was started.

```sh
./tools/phase06_prepare_secrets.sh --local-only \
  mqtt.example.invalid TEMP_PRIVATE_DIRECTORY
```

Result: PASS using the cached Mosquitto image. The validator accepted the
generated hash/cert files, and an independent assertion confirmed that the
PostgreSQL password contained no CR/LF bytes. Test credentials were deleted.

```sh
docker build --network=none --pull=false \
  -f infrastructure/rahti/mosquitto/Dockerfile \
  -t roadsense/mosquitto:phase06-check .
docker run --rm --network none --user 1001230000:0 ...
```

Result: PASS from a temporary minimal build context using the cached pinned
base image. UID `1001230000`, group `0` could create/remove a probe in the image
data directory. The temporary image/context were removed. This validates image
permissions only; Rahti's PVC/fsGroup behavior remains a live-cluster check,
which is why the manifest also fails startup if its PVC probe cannot write.

The full `tests/phase05_e2e.sh` was not rerun because the user's existing six
`roadsense-local` containers were healthy and active; that script deliberately
stops/recreates the stack and rotates its test credential. Disrupting the
active stack was not authorized. The complete changed Signal Processor suite
was run independently instead. The previously recorded Phase 05 evidence is
not relabeled as evidence for this commit.

## Required live verification (not performed)

- Rahti admission of the explicit local seccomp profile and all manifests.
- Actual arbitrary UID/fsGroup assignment and writable Mosquitto/PostgreSQL PVCs.
- Queued QoS 1 recovery while the Signal Processor is disconnected and across
  a broker Pod restart.
- PostgreSQL candidate-image startup, credential use, migration execution,
  repeat execution, backup/restore, and data persistence.
- Rahti quota, `standard-csi` availability, router namespace labels,
  passthrough MQTT/SNI behavior, allowlist enforcement, and API HTTPS access.
- VPS image pulls, private mounts, dashboard access, and full VPS-to-Rahti
  run trace.

These checks require explicit approval and access to the real targets. Until
then, Phase 06 is deployment-ready preparation, not a successful deployment.
