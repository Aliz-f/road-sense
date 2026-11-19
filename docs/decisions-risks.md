# Decisions, assumptions and risks

## Confirmed plan
- **Development and testing: the user's local laptop**, with **all seven application components on local Docker Compose**.
- **Final deployment: the user's personal VPS** runs MUHOS dataset, sensor-replay and dashboard using Docker Compose.
- **Final deployment: CSC Rahti** runs Mosquitto broker, signal-processor, road-analyzer, PostgreSQL and FastAPI with Kubernetes/OpenShift.
- Repository is documentation-only until Codex is instructed to implement one phase.
- Start with MUHOS Bosch IMU; CAN speed is a possible extension after unit/timing verification.
- No ML, LiDAR, cameras, ROS2, live vehicle or validated pothole detection.

## Checks still needed
1. Recheck precise course grading wording and required GitLab submission; laptop development plus remote split is our planned evidence.
2. Inspect actual supplied MUHOS recordings for schema, units, sample intervals, timestamps and sensor orientation.
3. Inspect laptop Docker prerequisites and disk resources.
4. Before remote deployment, verify personal VPS OS, RAM, disk, access method, firewall, DNS, security and data storage.
5. Check Rahti quotas, TLS/MQTT routing and persistent storage.
6. Verify CAN speed units and synchronization before correlating streams.
7. Choose secure dashboard and API access strategy.

## Risks / response
- **Local vs cloud grading interpretation:** clearly demonstrate full laptop Docker Compose integration and separately VPS↔Rahti communication; confirm exact official rules.
- **Misleading results:** report vibration statistics only, not certified road quality; speed, gravity and mounting orientation affect signals.
- **Time/unit confusion:** data profiling and numeric tests before processing.
- **Duplicates:** MQTT QoS1 + unique run/window keys and database upserts.
- **Remote exposure:** TLS, credential management, internal database, authenticated dashboard/API.
- **Deployment difficulties:** prove full stack locally, then publish versioned images and migrate in controlled steps.
- **Quota/data loss:** small sessions first, PVC backup/restore and planned rollback.
