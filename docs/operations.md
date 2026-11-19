# Deployment, security, and operations plan

## VPS — before installing or changing anything
Inventory OS, vCPU, RAM, disk, firewall, SSH access, Docker and Compose versions, domain and backup policy. Ask for explicit approval for firewall, SSH, DNS, package installation and public endpoints. Keep dataset directory restricted and mounted read-only. Limit dashboard to VPN/SSH tunnel or HTTPS + auth.

## Development deployment
First run broker and all application services on the VPS via Compose with service-only networking. Bind development ports to 127.0.0.1 and avoid public unauthenticated interfaces. Prove end-to-end functionality before migrating services.

## Rahti deployment
Check project namespace, quota, storage class, image registry, security context, route/TLS policy and image-pull credentials. Deploy PostgreSQL with PVC and backup, broker with verified TLS and ACL, processor and analyzer as Deployments, FastAPI behind authenticated HTTPS. Restrict DB to internal Service only. Set resource requests/limits, health probes and non-root containers.

## Final split
VPS Compose: sensor-replay and dashboard. Rahti: broker, processor, analyzer, PostgreSQL, API. VPS feeder calls broker outbound over MQTT/TLS; VPS dashboard calls API outbound HTTPS. Keep endpoints configurable via .env/secret injection, never hard-code credentials.

## Operations
Structured logs with service/run_id/sequence/window index (no raw sensitive samples). Monitor message counts, reconnects, invalid records, DB failures, API health. Provide startup, shutdown, tests, backup/restore, rolling update and rollback instructions. Use explicit cleanup safeguards to prevent unintentional deletion of data.

## Unknown until checked
VPS specs, public DNS, firewall rules, Rahti quota, TLS passthrough feasibility, course interpretation of VPS vs local computer, dataset license/citation. No deployment or environment configuration has been made.
