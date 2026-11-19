# Architecture — VPS plus CSC Rahti

## Goal
Remote VPS = external data producer plus presentation. Rahti = message broker, computation, persistence and API. A full Docker Compose topology is tested on VPS before cloud migration.

## Target locations
| Service | Where | Stack | Responsibility |
|---|---|---|---|
| sensor-replay | VPS | Python, Pandas, Paho MQTT, Docker | CSV batches from verified Bosch IMU recordings |
| dashboard | VPS | Streamlit, Plotly, Docker | Chart events via API |
| mqtt-broker | Rahti | Mosquitto | MQTT topic transport |
| signal-processor | Rahti | Python, NumPy/SciPy | Feature windows |
| road-analyzer | Rahti | Python | Rules and storage |
| postgres | Rahti | PostgreSQL + PVC | Sessions, runs, features, events |
| api | Rahti | FastAPI | Read-only API for dashboard |

## Data path
MUHOS CSV -> VPS sensor-replay -> outbound MQTT/TLS -> Rahti Mosquitto -> signal-processor -> feature message through broker -> road-analyzer -> PostgreSQL -> FastAPI -> outbound HTTPS API request by VPS Streamlit -> user browser.

## Networks and trust boundaries
- VPS: keep raw recordings in an access-controlled, read-only data mount. No MQTT broker or DB port publicly exposed.
- Rahti: broker external through verified TLS route, API HTTPS Route. All other components internal cluster Services.
- User to dashboard: private VPN/SSH tunnel initially; HTTPS plus authentication if public exposure is approved.
- All MQTT operations must authenticate/authorize topics. HTTPS alone does not replace API authorization.
- Confirm whether Rahti supports MQTT/TLS passthrough on intended external port; do NOT assume generic OpenShift HTTP Route carries native MQTT.
- First implementation uses one replica per MQTT consumer. Do not scale without a deliberate partitioning design.
- Preserve timestamps from source separately from replay wall-clock time.

## Kubernetes resources
Deployments for broker, processor, analyzer, API; Service for each needed internal endpoint; PVC for PostgreSQL; ConfigMaps for non-secret config, Secrets for credentials, probes/resources for reliability, limited Routes for broker/API.

## Non-goals
ROS2, LiDAR, raw camera videos, ML, GPS map, actual live vehicle sensor data, confirmed road-defect identification.
