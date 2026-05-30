# setup-tools.ps1
# Provisions or updates required tools via winget configure.
# Safe to rerun — winget configure is idempotent and will upgrade packages
# to the configured version if they are already installed.
#
# Installs current local ETL dependencies:
# - Python 3.11
# - uv
# - DuckDB CLI
# - Git
# - jq
#
# This script is run manually by choice; it is never called automatically
# by the ETL pipeline.
# If you or an agent needs to change installed tools, update
# .config/configuration.winget first instead of adding direct installs here.
#
# Run from the project root:
#   .\scripts\setup-tools.ps1

winget configure -f .config/configuration.winget --accept-configuration-agreements
