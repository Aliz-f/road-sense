# Environment templates

`local/.env` stores the Phase 01 private dataset root. Phase 02 generates
`local/.env.phase02` plus development TLS material under `local/runtime/`; both
are ignored by Git. Run `../../tools/prepare_phase02_local.sh` rather than
committing credentials. Every `.env` file is ignored by Git; `.env.example`
files contain no secrets.

The `vps` inventory points to separate Compose, dashboard, and replay examples
under `infrastructure/vps`; this prevents MQTT credentials from entering the
dashboard container. The `rahti` example is a variable-name inventory.
They do not authorize remote access, deployment, or secret creation.

Never commit credentials, certificates, private endpoints, or dataset files.
