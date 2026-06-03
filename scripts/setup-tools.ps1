# setup-tools.ps1
# Deprecated Windows-only wrapper.
#
# Use the Docker-first setup instead:
#   1) winget configure --file windows-bootstrap.dsc.yaml --accept-configuration-agreements
#   2) Open this repo in VS Code and run: Dev Containers: Reopen in Container
#
# This file is kept only so older instructions fail with a clear message
# instead of silently applying host-level setup.

throw 'setup-tools.ps1 is deprecated. Use the Docker-first devcontainer workflow described in README.md.'
