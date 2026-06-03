#!/usr/bin/env bash
set -euo pipefail

BASE="${HOME}/.local/share/fec-data"
mkdir -p "${BASE}/data" "${BASE}/db"

echo "Initialized persistent host paths:"
echo "  ${BASE}/data"
echo "  ${BASE}/db"
