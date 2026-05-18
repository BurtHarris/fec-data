# Copilot Instructions — FEC Campaign Finance ETL

## Project Summary

This is a batch ETL project that downloads Federal Election Commission (FEC) bulk data files and loads them into a local DuckDB database for analysis. The host OS is Windows. Bash scripts are run via Git Bash or WSL.

## Stack

- DuckDB CLI — local analytics database and SQL transforms
- curl — bulk file downloads
- bash — ETL orchestration scripts
- jq — JSON parsing in shell pipelines
- Windows (Git Bash or WSL for bash; PowerShell for git/admin tasks)
- winget — tool provisioning (`winget/fec-etl.dsc.yaml`)

## Key FEC Data Sources

- Bulk data portal: https://www.fec.gov/data/browse-data/?tab=bulk-data
- Electronic filing specs: https://www.fec.gov/campaign-finance-data/technical-specifications/
- FEC API (not currently used — documented for future reference only): https://api.open.fec.gov/developers/

## Repository Layout

```
data/raw/         # Downloaded source files — git-ignored, not committed
data/staging/     # Unpacked/normalized files — git-ignored
data/processed/   # Curated extracts — git-ignored
db/               # DuckDB .duckdb files — git-ignored
scripts/fetch/    # curl download scripts
scripts/transform/ # bash preprocessing (awk/sed/jq)
scripts/load/     # DuckDB load/orchestration scripts
sql/schema/       # DDL: CREATE TABLE statements
sql/transform/    # INSERT...SELECT / merge / cleanup SQL
sql/analysis/     # QA checks and ad hoc queries
logs/             # ETL run logs — git-ignored
tmp/              # Temp artifacts — git-ignored
winget/           # winget DSC provisioning YAML
```

## Common Commands

Provision tools (run once on a new machine):
```powershell
winget configure -f winget/fec-etl.dsc.yaml --accept-configuration-agreements --accept-package-agreements
```

Create the DuckDB database:
```bash
duckdb db/fec.duckdb ".databases"
```

Download a bulk file:
```bash
curl -L "https://www.fec.gov/files/bulk-downloads/2024/indiv24.zip" -o data/raw/indiv24.zip
```

Apply schema or transform SQL:
```bash
duckdb db/fec.duckdb -c ".read sql/schema/001_base_tables.sql"
duckdb db/fec.duckdb -c ".read sql/transform/010_load_individual_contributions.sql"
```

## Conventions

- `data/`, `db/`, `logs/`, `tmp/` are local runtime directories — never commit data files.
- SQL files use numeric prefixes for deterministic execution order: `001_`, `010_`, `020_`, etc.
- All scripts must be idempotent (safe to rerun).
- Raw source files in `data/raw/` are immutable — transformations happen downstream.
- Prefer SQL in `sql/transform/` over bash for data shaping logic.
- Log ETL runs to `logs/` with timestamps.

## Out of Scope (Current)

- FEC API ingestion (documented but not implemented)
- Scheduled/automated runs (manual execution only for now)