# Architecture — local laptop development → VPS + CSC Rahti production

## Three environments

1. **Laptop (development and testing):** Run *all* service containers via Docker Compose: sensor-replay, Mosquitto broker, signal-processor, road-analyzer, PostgreSQL, FastAPI and Streamlit. Develop, inspect and test end-to-end locally before any remote deployment.
2. **Personal VPS (final runtime):** Run only sensor-replay + Streamlit dashboard (and private mounted MUHOS recordings) with Docker Compose.
3. **CSC Rahti (final runtime):** Run Mosquitto, signal-processor, road-analyzer, PostgreSQL with PVC, and FastAPI through Kubernetes/OpenShift.

The VPS is the student's own server. This is not a teacher-owned server requirement.

## Service responsibility / final host
| Service | Local development | Final deployment | Responsibility |
|---|---|---|---|
| sensor-replay | laptop Compose | VPS Compose | MUHOS CSV → raw MQTT |
| dashboard | laptop Compose | VPS Compose | browser charts via HTTP API |
| mqtt-broker | laptop Compose | Rahti | MQTT routing with authentication |
| signal-processor | laptop Compose | Rahti | vibration window features |
| road-analyzer | laptop Compose | Rahti | rule-based events and persistence |
| postgres | laptop Compose | Rahti PVC | runs, feature windows, events |
| api | laptop Compose | Rahti | HTTP REST API for results |

## Development communication
```text
LAPTOP: MUHOS CSV → feeder → MQTT broker → processor → MQTT broker → analyzer
                                                      analyzer → PostgreSQL ← FastAPI ← dashboard ← browser
```
In local Compose all containers communicate over a private Docker network using Docker service names. Dashboard uses local FastAPI address. All services are fully tested locally.

Through Phase 05, the implemented local path is Sensor Replay → authenticated
TLS Mosquitto → Signal Processor → MQTT feature topic → Road Analyzer →
PostgreSQL → FastAPI → Streamlit/Plotly. Threshold events are published back to
the MQTT event topic. Sensor Replay also
sends a provenance-bound run-completion control message so the processor can
publish the final source-time window without stopping. The broker's one-message
QoS inflight limit and both subscribers' manual acknowledgements provide bounded
backpressure without blocking Paho network callbacks. The processor and analyzer
have no host ports and use read-only container filesystems. PostgreSQL is
internal-only and uses the named `roadsense-local-postgres-data` volume.
FastAPI performs only read-only, parameterized queries and the dashboard has no
database or MQTT access.

The Compose stack has two networks. `roadsense` is internal and carries MQTT,
database, analyzer, processor, and API database traffic. `browser` connects only
FastAPI and Streamlit and permits the explicitly loopback-bound host mappings
`127.0.0.1:8000` and `127.0.0.1:8501`. This split is required because the local
Docker engine does not publish ports attached only to an internal network.

The analyzer commits each event and its MQTT outbox payload atomically, then
publishes pending rows with QoS 1 and records completion. This closes the
database-commit/publication loss window while retaining deterministic
at-least-once event IDs. Rule versions are bound to exact heuristic semantics
and thresholds. Mosquitto stores the durable analyzer session and queued QoS 1
features in `roadsense-local-mqtt-data`, so broker and analyzer restarts do not
discard queued Phase 04 work.

## Final deployed communication
```text
PERSONAL VPS                                CSC RAHTI
MUHOS CSV → Feeder ─── MQTT/TLS ─────────→ Mosquitto → Processor
                                           ↑              |
                                           └── features ──┘
                                           ↓
                                          Analyzer → PostgreSQL ← API
Dashboard ←──────── HTTPS ───────────────────────────────┘
    ↑
 Browser (VPN or HTTPS with access control)
```

## Releasing locally tested software
Local tests pass → build versioned Docker images → push images to approved registry → deploy feeder/dashboard to personal VPS and backend to Rahti → switch environment variables to HTTPS/MQTT endpoints → verify complete remote trace. Reuse the same container images when possible; configuration differs by environment.

## Network and safety
- Keep data files private; in local development use local read-only dataset mounts; in VPS use private read-only server mount.
- Local Compose should bind external testing ports to loopback, not the internet.
- VPS feeder initiates **outbound MQTT over TLS** to Rahti broker. VPS dashboard initiates **outbound HTTPS** to Rahti FastAPI.
- Rahti database stays internal. Only tightly controlled MQTT TLS and API HTTPS endpoints are externally reachable. Validate actual OpenShift route capabilities before deploying.
- Dashboard protected by VPN/SSH tunnel or HTTPS+authentication, if exposed.
- Preserve raw recording timestamps and unique replay run IDs; handle MQTT QoS1 duplicate messages idempotently.
- One replica of each subscriber for MVP. No automatic pothole claims: outputs are exploratory vibration metrics.

## What belongs to Kubernetes?
Rahti Deployments, Services, ConfigMaps, Secrets, probes, resource limits, Routes for permitted external endpoints, and PostgreSQL persistent storage (PVC).

## Course assessment note
The project includes a true laptop-based local Docker execution **and** remote VPS↔Rahti communication. Check the official assessment language as part of Phase 00, but do not describe owning a personal VPS as a violation.
