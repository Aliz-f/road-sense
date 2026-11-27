# Validation, demo and course submission

## Acceptance

- The complete seven-service application passes locally with Docker Compose.
- Real CSV provenance, fields, units and source timestamps remain verified.
- Sensor Replay uses stable session_id, unique run_id and monotonic sequence IDs.
- Laptop-to-Rahti MQTT uses authenticated, CA-verified TLS through a
  loopback-only authenticated `oc port-forward`.
- Processor calculations, analyzer idempotency/outbox, database persistence,
  API contracts and dashboard features remain unchanged and tested.
- Rahti Pods, private Services and PVCs become healthy without a Route,
  LoadBalancer, NodePort or external database.
- A real run_id is visible from laptop replay through Rahti processing/storage
  and back to laptop Streamlit through the private API forward.
- Broker, processor and PostgreSQL restart/persistence evidence is recorded.
- No raw dataset, token, credential, key or generated Secret enters Git.

## Demonstration under ten minutes

Show the local Compose architecture and test evidence, then Rahti private
workloads/PVCs, the two loopback forwards, a laptop replay, the resulting API
data/dashboard and one recovery/idempotency safeguard. Clearly state the
exploratory-vibration limitation.

The official instructions checked on 2026-11-27 require a recorded demo of
about ten minutes with microphone and camera, introduction, project explanation
and step-by-step working commands. Recheck the current course README before
recording; do not rely on this summary if it changes.

## Submission

GitHub remains the development source. The official course repository requires
material in the student's private GitLab fork under `Final-Project/`, including
source/material, an architecture image and the demonstration link. Determine
the cleanest permitted way to reference or include this repository, then commit
and push the required course-fork changes. A GitHub PR alone is not submission.
