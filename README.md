# WSL2 + VS Code (WSL-First) Setup

This repository is configured for a Linux-first development workflow:

- Daily development runs entirely inside WSL (Ubuntu).
- Windows hosts only minimal tooling.
- Project files live in the Linux filesystem (for example, `~/projects/fec-data`).
- VS Code on Windows connects to VS Code Server in WSL.

## Repository Layout For Bootstrap

```text
/scripts
  bootstrap-wsl.sh
/devcontainer
  devcontainer.json
windows-bootstrap.dsc.yaml
README.md
```

## 1) Bootstrap The Windows Host (Minimal)

Prerequisite: run from an elevated Windows terminal.

```bash
winget configure --file windows-bootstrap.dsc.yaml --accept-configuration-agreements
```

This installs only host-level essentials:

- WSL
- VS Code
- Git Credential Manager
- Optional convenience utilities (Windows Terminal, PowerToys, 7-Zip)

## 2) Bootstrap WSL (Ubuntu)

Open Ubuntu (WSL), clone or move this repo under Linux home, then run:

```bash
cd ~/projects/fec-data
bash scripts/bootstrap-wsl.sh
```

What this script does:

- Installs base build tooling (`build-essential`, `git`, `curl`, `wget`, etc.)
- Creates `~/projects` if missing
- Configures Git identity (prompted once)
- Optionally generates an SSH key and prints next steps
- Includes clearly marked optional runtime blocks (Node, Python, Go, Rust)
- Includes an optional Docker block for in-WSL container workflows

## 3) Open In VS Code From WSL

Inside Ubuntu:

```bash
cd ~/projects/fec-data
code .
```

VS Code should open with the WSL indicator and install extensions into the WSL extension host.

## 4) Optional Dev Container Support

This repo includes a `devcontainer/devcontainer.json` for reproducible environments.

From a WSL-opened VS Code window:

1. Run `Dev Containers: Reopen in Container`.
2. Continue development in the containerized Linux environment.

## Why Windows-Specific Code Is Minimized

Keeping platform-specific logic out of the project avoids split setup paths, reduces drift between contributors, and makes builds/debugging predictable. The only expected Windows-specific artifact is `windows-bootstrap.dsc.yaml`, which bootstraps host prerequisites while all real development dependencies stay in Linux.

## Best Practices For WSL Development

- Keep repository files under Linux home directories, not mounted Windows paths.
- Run all package managers, compilers, and databases inside WSL.
- Use `code .` from WSL so VS Code Server and extensions run in Linux.
- Keep shell scripts idempotent and rerunnable.
- Use SSH-based Git auth inside WSL; keep credentials out of scripts.
