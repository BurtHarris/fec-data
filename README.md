# Docker + VS Code Dev Container (Docker-First)

This repository is configured for a Docker-first workflow using VS Code Dev Containers.

- Daily development runs in a Linux dev container.
- Windows-specific setup is limited to installing Docker Desktop (plus VS Code) via Winget Configure.
- Project dependencies and tooling are provisioned inside the container through `scripts/setup-tools.sh`.

## Repository Layout For Bootstrap

```text
/scripts
  setup-tools.sh
/.devcontainer
  devcontainer.json
windows-bootstrap.dsc.yaml
README.md
```

## 1) Bootstrap Windows Host (Docker Prerequisites)

Run from an elevated Windows terminal:

```bash
winget configure --file windows-bootstrap.dsc.yaml --accept-configuration-agreements
```

This installs host-level prerequisites only:

- Docker Desktop
- Visual Studio Code

## 2) Open In VS Code Dev Container

From VS Code:

1. Open this repository folder.
2. Run `Dev Containers: Reopen in Container`.
3. Wait for post-create setup to finish.

The container setup runs `bash scripts/setup-tools.sh`, which installs project CLI dependencies in the Linux container.

If you already had this container open before these settings were added, run the bootstrap once manually:

```bash
bash scripts/setup-tools.sh
```

## 3) Verify Tooling Inside The Container

Open a terminal in the container and verify:

```bash
uv --version
duckdb --version
```

## Why This Is Docker-First

The development runtime is the container, not the host OS. This keeps contributor environments consistent and avoids host-specific dependency drift.

Windows artifacts are intentionally limited to Docker-host provisioning via `windows-bootstrap.dsc.yaml`.
