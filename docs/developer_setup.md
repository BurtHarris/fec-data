# Developer Setup

Dev Containers package a reproducible Linux development environment with pinned tools, extensions, and runtime behavior. For this ELT project, that matters because large FEC downloads and DuckDB database builds are sensitive to filesystem performance and environment drift. Running inside a container keeps setup consistent across contributors and avoids the performance penalties of heavy I/O against Windows-mounted paths.

## Docker-First Workflow

This repository is configured for a Docker-first workflow using VS Code Dev Containers.

- Daily development runs in a Linux dev container.
- Windows-specific setup is limited to installing Docker Desktop (plus VS Code) via Winget Configure.
- Project dependencies and tooling are provisioned inside the container through scripts/setup-tools.sh.

## Repository Layout For Bootstrap

```text
/scripts
  setup-tools.sh
/devcontainer
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

## 2) Clone Into A Container Volume (Recommended)

Use this approach for best performance with large ELT files and DuckDB workloads.

From VS Code:

1. Run Dev Containers: Clone Repository in Container Volume.
2. Paste the repository URL.
3. Let VS Code clone into the Docker-managed volume and open it in the container.
4. Wait for post-create setup to finish.

Why this is preferred:

- Keeps source and runtime files on Linux/container storage.
- Avoids slower Windows bind mounts for heavy database and file I/O.
- Reduces warnings about mounted-filesystem performance.

## 3) If You Already Cloned On Windows

If you opened a Windows folder first and then reopened in container, you may still be on a Windows-backed bind mount.

To correct it:

1. In VS Code, run Dev Containers: Clone Repository in Container Volume.
2. Reclone the repository using that command.
3. Re-run setup after opening the new container workspace.

## 4) Verify Tooling Inside The Container

Open a terminal in the container and verify:

```bash
bash scripts/setup-tools.sh
uv --version
duckdb --version
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

## Operational Notes

- Build DuckDB databases under project paths like db/, data/, logs/, and tmp/ inside the container workspace.
- Avoid /mnt/c paths for large imports, transforms, and database writes.
