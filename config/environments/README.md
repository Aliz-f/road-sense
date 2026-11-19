# Environment templates

Only `local/.env.example` is used during Phases 01-05. Copy it to
`local/.env`, replace the dataset root with an absolute private path, and set
future credentials locally when their services are introduced. Every `.env`
file is ignored by Git; `.env.example` files contain no secrets.

The `vps` and `rahti` examples are variable-name inventories for Phase 06.
They do not authorize remote access, deployment, or secret creation.

Never commit credentials, certificates, private endpoints, or dataset files.
