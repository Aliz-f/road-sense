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
- single-replica `Recreate` rollout strategies for both MQTT subscriber
  Deployments, preventing overlapping Pods from sharing their fixed persistent
  MQTT client identities during an update;
- Rahti's current explicit `Localhost/rahti-custom-seccomp.json` profile and
  resource request/limit ratios no greater than five;
- a fresh generate-name migration Job per execution, database advisory
  locking/checksums, a release-derived migration ID, and an apps-stage success
  marker gate;
- separate VPS Compose interpolation, dashboard, and Sensor Replay files so
  MQTT credentials are not injected into Streamlit;
- an init-container write/remove check for Mosquitto's PVC under the assigned
  UID/fsGroup model;
- rendered manifest structure tests, stricter CIDR validation, server-side
  dry-run gates, processor/PostgreSQL readiness checks, and broader Docker
  context exclusions;
- repository-wide Docker exclusions for every `.env`/`.env.*` file, including
  private `infrastructure/vps/sensor-replay.env` and dashboard configuration;
- replacement of the unsupported raw-MQTT Route with an approval-gated Rahti
  LoadBalancer Service on port 30883, restricted to the VPS egress CIDR; and
- a durable SQLite input journal for the Signal Processor. Raw deliveries are
  journaled before processing/acknowledgement and recovered in broker order
  before readiness, while deterministic analyzer upserts absorb republished
  results after an ambiguous crash;
- lock-protected readiness transitions that require connection, subscription,
  and completed initial recovery at the same instant, preventing a disconnect
  during recovery from recreating the readiness file; and
- schema-v2 bounded rejected-input tombstones. Rejected payload bytes are
  removed immediately, the newest 1,024 topic/hash pairs are retained for
  exact-redelivery suppression, and pending/accepted recovery rows are never
  affected. With broker inflight limited to one, an unacknowledged rejection
  cannot be evicted before redelivery; existing schema-v1 rejected rows migrate
  transactionally.

The seccomp and UID/fsGroup choices were checked against the current
[CSC workload security documentation](https://docs.csc.fi/cloud/rahti/configurations/workload-security/).
The PVC assumptions were checked against
[CSC persistent storage documentation](https://docs.csc.fi/cloud/rahti/usage/storage/persistent/).
These documents describe policy; only the actual project can prove admission,
storage permissions, and runtime behavior.

CSC documents Routes as HTTP/HTTPS ingress. The raw MQTT design now follows
the separately documented
[Rahti LoadBalancer Service procedure](https://docs.csc.fi/cloud/rahti/configurations/loadbalancer-service/),
which requires Service Desk approval and project-specific external networking.
The manifests encode the documented external port range, disabled node ports,
local external traffic policy, broker node selector, and source CIDR policy;
none of those Rahti-specific assumptions was exercised against a cluster.

## Offline verification performed

Commands were run from the Phase 06 worktree. Outputs below are summarized and
contain no credentials.

```sh
python3 -m unittest discover -s tests -p 'test_phase06_preparation.py' -v
```

Result: PASS, 10 tests. This rendered and structurally checked private manifests
and checked immutable images, API Route/MQTT LoadBalancer separation, CIDR
inputs, Secret byte consistency, Rahti seccomp and Mosquitto PVC safeguards,
migration identifiers, processor state persistence, both MQTT subscriber
rollout strategies, VPS configuration separation, and Docker build-context
exclusions including `sensor-replay.env`.

```sh
docker create ... roadsense/signal-processor-test:phase03-local ...
docker cp services/signal-processor/{src,tests} ...
docker start -a roadsense-phase06-processor-unit
```

Result: PASS, 35 tests in a cached test image. This includes persistent-session
construction, resubscription, readiness cleanup, client-ID validation,
source-time processing, disconnect-during-recovery readiness exclusion,
durable journal reopen/deduplication/pruning, bounded rejected tombstones,
schema-v1 migration, crash recovery with the original window indices,
deliberate non-finalization of partial runs at shutdown, duplicate handling,
completion, gap and schema behavior.

```sh
for file in tools/phase06_*.sh; do bash -n "$file"; done
python3 -m py_compile tools/phase06_render_rahti.py \
  tools/phase06_validate_secret_files.py \
  services/signal-processor/src/signal_processor/{config,mqtt_service,health,state}.py
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

The complete local acceptance sequence was then run from a disposable checkout
with ignored credentials copied only for the test and removed afterward:

```sh
./tests/phase02_e2e.sh
./tests/phase02_reconnect_e2e.sh
./tests/phase03_e2e.sh
./tests/phase04_e2e.sh
./tests/phase05_e2e.sh
```

Result: PASS. Phase 02 passed its 21 unit tests, authenticated real-MUHOS replay,
anonymous rejection, and reconnect case. Phase 03 passed all 31 processor unit
tests, real-data/rate/backpressure checks, and the new active-replay crash
regression: the processor was sent SIGKILL after feature publication, restarted
from its journal, and the subscriber observed exactly 19 feature windows with
contiguous indices 0 through 18. Phase 04 passed database, broker-session,
transactional-outbox, credential rotation, repeatable migration, and recovery
checks. Phase 05 passed its 11 API and 7 dashboard tests plus the complete
real-MUHOS API/dashboard failure-and-recovery smoke test. The scripts shut down
their test containers; persistent local test volumes remain by design.

For the readiness/retention follow-up, the affected current suite was rerun:

```sh
python3 -m py_compile services/signal-processor/src/signal_processor/*.py \
  services/signal-processor/tests/*.py
docker start -a roadsense-phase06-review-processor-unit
./tests/phase03_e2e.sh
git diff --check
```

Result: PASS. The disposable unit container ran 35 tests. The Phase 03 Compose
suite rebuilt the processor, reran the same 35 tests, verified real-data
features and replay-rate invariance, passed queue-capacity-one backpressure,
and again passed the active-replay SIGKILL recovery with 19 contiguous feature
windows. The disposable container and checkout (including copied ignored test
credentials) were removed afterward. No remote service was contacted.

The Docker build logs showed filtered contexts (for example, 47.76 kB for the
Signal Processor and 32.33 kB for Sensor Replay). This is supporting evidence,
not a substitute for the static exclusion regression above.

## Rollout-strategy follow-up verification

The final deployment-preparation fix added `strategy.type: Recreate` to the
single-replica `road-analyzer` Deployment. The existing single-replica Signal
Processor `Recreate` strategy was not changed. A regression test renders
`apps.yaml.tpl`, locates Deployments by `metadata.name`, and requires both MQTT
subscribers to retain this configuration.

The current branch reran the following offline checks:

```sh
python3 -m unittest discover -s tests -p 'test_phase06_preparation.py' -v
env PYTHONPATH=services/signal-processor/src \
  python3 -m unittest discover -s services/signal-processor/tests -v
docker run --rm --network none --entrypoint python ... \
  roadsense/signal-processor-test:phase03-local \
  -m unittest discover -s /app/tests -v
./tools/phase06_preflight.sh local
docker compose --env-file .env -f compose.yaml config --quiet
python3 -m py_compile ...
for file in tools/phase06_*.sh; do bash -n "$file"; done
git diff --check
```

Result: PASS for the 10 Phase 06 preparation tests, all 35 Signal Processor
tests in the cached network-disabled test image, local toolchain preflight, VPS
Compose expansion from the three example environment files, Python compilation,
shell syntax, and whitespace checks. A direct host run passed 29 tests but could
not import the MQTT test module because `paho-mqtt` is not installed on the
host; no package was installed, and the complete cached-image run passed.

All rendered private manifests parsed as YAML objects with `apiVersion` and
`kind`, and structural assertions confirmed that both `signal-processor` and
`road-analyzer` have one replica and `strategy.type: Recreate`. A local
`kubectl create --dry-run=client --validate=false` could not finish because the
installed client still attempted API discovery against an unavailable local
cluster. No Rahti connection was attempted. Server-side dry-run and admission
remain required live checks.

The branch changes only deployment configuration, project status documentation,
this report, and the rollout regression test. Application functionality, MQTT
contracts, database schemas, and API endpoints are unchanged.

## Required live verification (not performed)

- Rahti admission of the explicit local seccomp profile and all manifests.
- Actual arbitrary UID/fsGroup assignment and writable Mosquitto/PostgreSQL PVCs.
- Processor journal persistence, recovery ordering, readiness, and PVC
  permissions under Rahti's assigned UID after a real Pod crash. Local
  SIGKILL recovery and MQTT reconnect behavior passed, but were not run in
  Rahti.
- PostgreSQL candidate-image startup, credential use, migration execution,
  repeat execution, backup/restore, and data persistence.
- Rahti quota, `standard-csi` availability, router namespace labels, Service
  Desk LoadBalancer approval/allocation, the broker node label, external port
  30883, client source-IP preservation, NetworkPolicy allowlisting, MQTT TLS,
  and API HTTPS access.
- VPS image pulls, private mounts, dashboard access, and full VPS-to-Rahti
  run trace.

These checks require explicit approval and access to the real targets. Until
then, Phase 06 is deployment-ready preparation, not a successful deployment.
