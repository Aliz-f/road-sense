# Phase 06 — VPS (deployment preparation only)

This folder will run **only** Sensor Replay (one-shot) and Streamlit (long-running).
No VPS actions have been taken by this change.

## What the commands teach
- `docker compose config --quiet` renders/checks the configuration (do not print secrets).
- `docker compose pull` downloads immutable published images.
- `docker compose up -d --wait dashboard` runs Streamlit privately on 127.0.0.1.
- `docker compose run --rm sensor-replay` replays exactly one source run.
- `docker compose logs`, `ps` and `down` inspect and stop containers.

## Preconditions
1. **Explicit owner approval** for any VPS package/install/firewall/SSH/DNS/deployment changes.
2. VPS supports Docker Engine and Compose; verify CPU, RAM, disk, OS/architecture.
3. Copy the private dataset to a restricted path (e.g. `/srv/roadsense/archives`).
4. Copy a trusted broker CA certificate to `/srv/roadsense/certs/ca.crt`.
5. Create ignored `.env`, `dashboard.env`, and `sensor-replay.env` from their
   examples and `chmod 600` all three. Keep API settings out of Sensor Replay
   and MQTT credentials out of the dashboard.
6. Confirm approved access method for the dashboard: **SSH tunnel only initially**.
7. Confirm CSC assigned the Rahti LoadBalancer ingress IP and that its DNS,
   certificate hostname, and external port `30883` match. Do not use a Route
   for raw MQTT.

```sh
# ON YOUR VPS, in a private clone of the release repository:
cd infrastructure/vps
cp .env.example .env
cp dashboard.env.example dashboard.env
cp sensor-replay.env.example sensor-replay.env
chmod 600 .env dashboard.env sensor-replay.env
# Edit .env securely; DO NOT commit, display, or paste it
docker compose --env-file .env -f compose.yaml config --quiet
docker compose --env-file .env -f compose.yaml pull
docker compose --env-file .env -f compose.yaml up -d --wait dashboard
docker compose --env-file .env -f compose.yaml ps
docker compose --env-file .env -f compose.yaml run --rm sensor-replay
docker compose --env-file .env -f compose.yaml logs --tail=50 dashboard
```

From your laptop, access the VPS dashboard without exposing it publicly:

```sh
ssh -L 8501:127.0.0.1:8501 USER@VPS_HOST
# open http://127.0.0.1:8501 locally, in another terminal/browser
```

## Rollback and safety
Do not use `down -v`, `docker system prune`, or destructive host commands.
To roll back, restore the last known-good image digests in `.env` then
`docker compose --env-file .env -f compose.yaml up -d --wait --no-deps dashboard`.
`sensor-replay` has no automatic restart and must be run manually with a fresh run_id.
Keep archives private, read-only in the container, and never commit `.env` or keys.

For deployment ordering and Rahti commands, see `../../docs/phase-06-deployment-guide.md`.
