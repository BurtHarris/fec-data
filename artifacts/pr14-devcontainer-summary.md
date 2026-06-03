Summary:
- Moved the persistence setup into the active VS Code Dev Container path under `.devcontainer/`.
- Added `.devcontainer/scripts/init-host-paths.sh` and updated `.devcontainer/devcontainer.json` to use the persistent `data/` and `db/` bind mounts plus `FEC_DATA_DIR` / `FEC_DB_DIR`.
- Updated `docs/developer_setup.md` so the setup and rebuild guidance now consistently points to `.devcontainer/devcontainer.json`.
- Marked `devcontainer/devcontainer.json` as a transitional copy to make it clear `.devcontainer/` is the source of truth.

Concise reply:
Thanks — I addressed the devcontainer path mismatch that was making the persistence changes ambiguous. The active config now lives under `.devcontainer/`, the docs were updated to match, and the legacy `devcontainer/` config is now marked as transitional so reviewers can see which path is authoritative.
