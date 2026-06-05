# Developer Setup

Dev Containers package a reproducible Linux development environment with pinned tools, extensions, and runtime behavior. For this ELT project, that matters because large FEC downloads and DuckDB database builds are sensitive to filesystem performance and environment drift. Running inside a container keeps setup consistent across contributors while isolating heavy runtime I/O in persistent Docker volumes.

## Docker-First Workflow

This repository is configured for a Docker-first workflow using VS Code Dev Containers.

- Daily development runs in a Linux dev container.
- Windows-specific setup is limited to installing Docker Desktop (plus VS Code) via Winget Configure.
- Project dependencies and tooling are provisioned during devcontainer image build.

## Repository Layout For Bootstrap

```text
/.devcontainer
  Dockerfile
  devcontainer.json
windows-bootstrap.dsc.yaml
/docs
  developer_setup.md
README.md
```

## 1) Bootstrap Windows Host (Docker Prerequisites)

Linux-centric developers can skip this step if Docker and VS Code are already installed on their machine.

Run from an elevated Windows terminal:

```bash
winget configure --file windows-bootstrap.dsc.yaml --accept-configuration-agreements
```

This installs host-level prerequisites only:

- Docker Desktop
- Visual Studio Code

## 2) Open The Repository In A Dev Container

Use your normal repository checkout and open it in a Dev Container.

From VS Code:

1. Open the repository folder.
2. Run Dev Containers: Reopen in Container.
3. Wait for post-create setup to finish.

Storage model used by this repo:

- Repository source files remain in the workspace checkout.
- High-I/O runtime directories use persistent Docker volumes:
  - `fec-data-data` -> `/workspaces/fec-data/data`
  - `fec-data-db` -> `/workspaces/fec-data/db`

This preserves normal Git/editor workflow while avoiding host path translation issues across Docker backends.

## 3) Apply Updated Devcontainer Mounts (One-Time)

If you pulled recent changes to `.devcontainer/devcontainer.json`, rebuild once to apply new mounts.

From VS Code:

1. Run Dev Containers: Rebuild Container.
2. Reopen the workspace after rebuild completes.
3. Continue with normal start/stop tasks.

## 4) Verify Tooling And Storage Inside The Container

Open a terminal in the container and verify:

```bash
uv --version
duckdb --version
python --version
python -c "from airflow.providers.http.hooks.http import HttpHook; from airflow.providers.sqlite.hooks.sqlite import SqliteHook; from airflow_provider_duckdb.hooks.duckdb_hook import DuckDBHook; print('airflow adapters: http/sqlite/duckdb ready')"
echo "$FEC_DATA_DIR"
echo "$FEC_DB_DIR"
```

## 5) Launch And Stop From VS Code

This repo includes a simplified task workflow so daily usage is two commands.

From VS Code:

1. Run task: `Start: stack + open UIs`
2. Run task when done: `Stop: stack services`

What start does:

- Runs Airflow setup (`scripts/airflow-setup.sh`)
- Starts Airflow scheduler and webserver
- Starts the ops web app on `http://127.0.0.1:8787`
- Opens external browser tabs for:
  - `http://127.0.0.1:8080` (Airflow UI)
  - `http://127.0.0.1:8787` (ops web UI)

Implementation note:

- Only `Start: stack + open UIs` and `Stop: stack services` are intended for regular use.
- Helper tasks are kept hidden in the task picker and can be regenerated later if needed.

Optional task:

- Run `Export: db snapshot` to copy database files to `exports/db` for host-side tools.

## Operational Notes

- `data/` and `db/` persist across container restarts/rebuilds because they are mounted from Docker volumes.
- Treat Docker volumes as source of truth for runtime artifacts.
- Use exported snapshots (`exports/db`) when you need to consume DB files from host-side Windows tools.
- Avoid `/mnt/c` paths for large imports, transforms, and database writes.
