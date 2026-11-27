# Operations — laptop and CSC Rahti

## Complete local application

Prepare the private local environment, then use the unchanged Compose stack:

```sh
./tools/prepare_phase02_local.sh /absolute/path/to/private/MUHOS/archives
docker compose --env-file config/environments/local/.env.phase02 \
  -f infrastructure/compose/local.compose.yaml config --quiet
./tests/phase05_e2e.sh
```

Only FastAPI and Streamlit bind laptop loopback. MQTT and PostgreSQL remain on
private Docker networks. Routine cleanup must not remove named persistence
volumes unless data deletion is explicitly intended and approved.

## Rahti preparation and deployment

Run `./tools/phase06_preflight.sh rahti` only after logging in with `oc` and
setting the exact existing namespace. Verify quota, SCC, storage class, image
pull access and create permissions. Publish immutable backend images only after
approval; render manifests locally; then deploy in the guarded sequence:

```sh
./tools/phase06_rahti.sh secrets --execute
./tools/phase06_rahti.sh core --execute
./tools/phase06_rahti.sh migrate --execute
./tools/phase06_rahti.sh apps --execute
./tools/phase06_rahti.sh status --execute
```

Each remote command also requires `ROAD_SENSE_APPROVED=yes`; see the detailed
guide. Stop on the first failure. Do not create Routes or LoadBalancers.

## Private laptop-to-Rahti demo

Keep these in separate terminals for the duration of the demo:

```sh
oc -n "$RAHTI_NAMESPACE" port-forward --address 127.0.0.1 service/mqtt-broker 18883:8883
oc -n "$RAHTI_NAMESPACE" port-forward --address 127.0.0.1 service/api 18000:8000
```

Use `rahti-client.compose.yaml` over the normal local file. The MQTT broker
certificate must contain `DNS:localhost`, and the laptop client mounts the
matching CA certificate. Never use an insecure TLS flag.

## Recovery

- Record the prior image digests before rollout and use `oc rollout history`
  and selective `oc rollout undo` for compatible application rollbacks.
- Never delete PVCs as rollback. Back up PostgreSQL, Mosquitto and processor
  state before disruptive tests.
- Migration rollback requires a verified database restore plan; do not assume
  SQL migrations are reversible.
- Stop the two `oc port-forward` processes to close laptop access. They create
  no persistent or public endpoint.
- Sanitize logs and preserve run IDs, image digests and exact commands in the
  Phase 06 implementation evidence.
