# Environment templates

`local/.env` stores the Phase 01 private dataset root. Phase 02 generates
`local/.env.phase02` plus development TLS material under `local/runtime/`; both
are ignored by Git. Run `../../tools/prepare_phase02_local.sh` rather than
committing credentials. Every `.env` file is ignored by Git; `.env.example`
files contain no secrets.

The `rahti` example is a variable-name inventory for in-cluster workloads.
Phase 06 laptop clients use the protected, ignored
`infrastructure/compose/rahti-client.env` described by its committed example.
The `vps` inventory is abandoned historical material and is not in the active
deployment path. None of these files authorizes remote access, deployment, or
secret creation.

Never commit credentials, certificates, private endpoints, or dataset files.
