# Architecture — local laptop + CSC Rahti

## Environments

1. **Local Linux laptop:** the complete seven-service application runs with
   `infrastructure/compose/local.compose.yaml` for development, integration
   tests and a fully local demonstration.
2. **CSC Rahti:** Mosquitto, Signal Processor, Road Analyzer, PostgreSQL/PVC and
   FastAPI run as private OpenShift workloads.
3. **Distributed demonstration:** the laptop runs only Sensor Replay and
   Streamlit using the small `rahti-client.compose.yaml` override. Authenticated
   `oc` sessions forward laptop loopback ports to Rahti ClusterIP Services.

There is no active VPS deployment and no additional Kubernetes cluster.

| Service | Complete local mode | Distributed demo |
|---|---|---|
| Sensor Replay | laptop Compose | laptop Compose client |
| Streamlit | laptop Compose | laptop Compose client |
| Mosquitto | laptop Compose | Rahti Deployment + PVC |
| Signal Processor | laptop Compose | Rahti Deployment + PVC |
| Road Analyzer | laptop Compose | Rahti Deployment |
| PostgreSQL | laptop Compose volume | Rahti Deployment + PVC |
| FastAPI | laptop Compose | Rahti Deployment |

## Data flows

```text
COMPLETE LOCAL
CSV → Sensor Replay → MQTT/TLS → Processor → MQTT → Analyzer → PostgreSQL
                                                               ↓
Browser ← Streamlit ← FastAPI ←─────────────────────────────────┘

DISTRIBUTED DEMO
LAPTOP                                      CSC RAHTI
CSV → Sensor Replay → 127.0.0.1:18883 ─oc→ Mosquitto → Processor
                                               ↑          ↓
                                               └ features ┘
                                                     ↓
                                                  Analyzer → PostgreSQL ← FastAPI
Browser ← Streamlit ← 127.0.0.1:18000 ───────oc───────────────────────┘
```

The MQTT forward is still end-to-end TLS at the application layer. Sensor
Replay verifies a private CA and a server certificate containing `localhost`
as a DNS SAN, then authenticates with the Rahti broker credential. `oc
port-forward` adds authenticated OpenShift transport and binds only to
`127.0.0.1`. The API forward carries HTTP inside that authenticated local
tunnel; the unauthenticated API is never publicly routed.

The Compose override uses host networking for only the two laptop client
containers so they can reach loopback-bound forwards. It resets their local
broker/API dependencies and published-port mapping; Streamlit itself still
listens only on laptop loopback port 8501. The normal Compose file is unchanged and retains
its private `roadsense` network, browser network, loopback API/dashboard ports,
named MQTT/PostgreSQL/processor volumes, read-only filesystems and health gates.

## Reliability and security invariants

- MQTT topics, payloads and run_id/sequence_id semantics are unchanged.
- MQTT requires TLS and authentication. TLS verification is never disabled.
- PostgreSQL is ClusterIP-only and accepted only from API/analyzer/migration Pods.
- Mosquitto, PostgreSQL and processor state use RWO PVCs; one processor and one
  analyzer replica preserve stable sessions and deterministic recovery.
- Analyzer database/outbox commits remain atomic and idempotency keys remain intact.
- The Rahti private baseline contains no Route, LoadBalancer or NodePort. The
  broker no longer selects special LoadBalancer nodes.
- Live Rahti SCC, storage, NetworkPolicy/port-forward behavior, image pulls,
  persistence and restart recovery remain deployment-time checks.

The archived `routes.yaml.tpl`, `mqtt-external.yaml.tpl` and
`infrastructure/vps` record the abandoned earlier design. Current render/apply
tools cannot select them.
