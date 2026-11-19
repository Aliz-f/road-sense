# Environment templates

`local/.env` stores the Phase 01 private dataset root. Phase 02 generates
`local/.env.phase02` plus development TLS material under `local/runtime/`; both
are ignored by Git. Run `../../tools/prepare_phase02_local.sh` rather than
committing credentials. Every `.env` file is ignored by Git; `.env.example`
files contain no secrets.

The `vps` and `rahti` examples are variable-name inventories for Phase 06.
They do not authorize remote access, deployment, or secret creation.

Never commit credentials, certificates, private endpoints, or dataset files.
