#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="${FEC_DB_DIR:-$PWD/db}"
OUT_DIR="$PWD/exports/db"

mkdir -p "$OUT_DIR"

# Copy DuckDB artifacts for host-side tools.
find "$SRC_DIR" -maxdepth 1 -type f \( -name "*.duckdb" -o -name "*.sqlite" -o -name "*.db" \) -print0 \
  | while IFS= read -r -d '' file; do
      cp -f "$file" "$OUT_DIR/"
    done

echo "Export complete: $OUT_DIR"
