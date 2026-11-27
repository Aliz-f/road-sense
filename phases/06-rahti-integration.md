# Phase 06 — Deploy the backend to CSC Rahti and demonstrate from the laptop

## Goal

Keep the verified complete laptop Compose application, deploy its backend to
CSC Rahti, and demonstrate laptop Sensor Replay and Streamlit communicating
with private Rahti Services through authenticated loopback port-forwards.

## Prerequisites

- Phase 05 local end-to-end checks pass.
- Existing Rahti namespace and authenticated `oc` access.
- Verified project quota, SCC, storage class and registry image-pull access.
- Approved registry plus immutable backend/PostgreSQL image digests.
- Explicit approval before image publishing, secret creation or Rahti changes.

## Tasks

1. Re-run local Compose validation and affected integration checks.
2. Inspect Rahti capabilities without changing the project.
3. Build and publish only the four Rahti application images after approval.
4. Generate protected MQTT TLS/authentication and PostgreSQL credentials
   locally; use a broker certificate with `DNS:localhost` for the demo forward.
5. Render and review private core, migration and application manifests.
6. Deploy Secrets, core, migration and apps in guarded order after approval.
7. Start loopback-only MQTT/API `oc port-forward` sessions on the laptop.
8. Run existing Sensor Replay and Streamlit Compose services with the
   `rahti-client.compose.yaml` override.
9. Record a run_id trace, persistence/restart evidence and sanitized logs.

Do not deploy a VPS, public Route, LoadBalancer, NodePort, external DNS, gateway
or additional Kubernetes cluster. Do not change processing algorithms,
contracts, database schema, dashboard behavior or recovery semantics.

## Deliverables

Private Rahti manifests, immutable image settings, guarded deployment scripts,
laptop client override, exact commands, sanitized evidence and rollback notes.

## Acceptance criteria

- [x] Complete local Compose path remains available and configuration validates.
- [x] Active Rahti templates contain private Services/PVCs and no public resource.
- [x] Broker has no LoadBalancer-specific node selector.
- [x] Active tools cannot render/apply the abandoned public/VPS path.
- [x] Laptop demo configuration uses loopback `oc port-forward`, MQTT auth and TLS verification.
- [ ] Real Rahti Pods, PVCs, SCC behavior, image pulls and migrations verified.
- [ ] Laptop-to-Rahti replay/API/dashboard trace verified with a real run_id.
- [ ] PostgreSQL, broker session and processor journal persistence verified after controlled restarts.
- [ ] Sanitized live implementation report completed.

Repository preparation does not satisfy the unchecked live criteria. Stop
before Phase 07.
