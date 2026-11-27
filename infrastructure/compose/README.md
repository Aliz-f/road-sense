# Docker Compose

`local.compose.yaml` is the unchanged complete laptop application: Sensor
Replay, authenticated TLS Mosquitto, Signal Processor, Road Analyzer,
PostgreSQL, FastAPI and Streamlit plus migrations and test helpers. Only FastAPI
and Streamlit publish loopback ports. MQTT/PostgreSQL remain private, and named
volumes retain broker, processor and database state.

`rahti-client.compose.yaml` is a small Phase 06 override for the distributed
demo. It runs only Sensor Replay and Streamlit, resets their local backend
dependencies and lets the Linux containers reach laptop-loopback `oc
port-forward` sockets with host networking. It does not define another laptop
stack or change application contracts.

Copy `rahti-client.env.example` to the ignored `rahti-client.env`, protect it
with mode 600, and follow `../../docs/phase-06-deployment-guide.md`. MQTT still
uses authentication and CA-verified TLS. No public endpoint is involved.

`preflight.compose.yaml` is the Phase 01 daemon/lifecycle check and contains no
RoadSense application service.
