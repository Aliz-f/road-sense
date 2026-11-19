# Validation, demo and course submission

## End-to-end acceptance
- Verified real CSV fields/time/units, sample count, and dataset citation.
- Replay on VPS emits topic batches with stable session_id, unique run_id, sequence and source timestamps.
- MQTT broker receives authenticated messages and forwards to Rahti processor.
- Numeric RMS and peak calculations tested against known synthetic signals.
- Analyzer creates versioned events and persists rows; reprocessing identical window stays idempotent.
- FastAPI lists runs, features and events; dashboard charts recorded values and clearly states this is not validated pothole detection.
- Rahti Pods/Services/Routes/PVC healthy; cross-environment trace from VPS to Rahti and back.
- Restart/reconnect and recovery tests documented.
- No raw datasets, tokens, credentials or unprotected public DB endpoints.

## Proposed demonstration under ten minutes
0–1: introduction & goal. 1–2: diagram and data file. 2–3: VPS Docker Compose feeder. 3–5: Rahti Pods/MQTT processing. 5–7: API, database and dashboard. 7–8.5: compare two sessions and discuss speed. 8.5–9.5: reconnect/duplicate or failure recovery. 9.5–10: recap. Recheck exact current video/audio/camera rules directly in the course README.

## Course submission
GitHub road-sense = working repository. Verify whether official course submission requires copying to GitLab fork under Final-Project/, architecture image arch.png, open-source.url, video-demonstration.url, deadlines, and camera/mic use. Never assume a GitHub repo link alone satisfies the official submission. Cite MUHOS and original research under its verified license. Keep a sanitized evidence report.
