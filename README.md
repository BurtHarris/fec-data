# FEC Campaign Finance ETL (DuckDB + curl + PowerShell on Windows)

This repository is set up for an ETL workflow that downloads Federal Election Commission (FEC) campaign finance ZIP files, manages them locally, and loads modeled tables directly into DuckDB native storage.

## Key FEC Links

- Bulk data portal: https://www.fec.gov/data/browse-data/?tab=bulk-data
- API landing page: https://www.fec.gov/developers/
- API documentation: https://api.open.fec.gov/developers/
- Campaign finance data (browse): https://www.fec.gov/data/
- Candidate master file and data catalogs: https://www.fec.gov/campaign-finance-data/
- Electronic filing specifications (formats): https://www.fec.gov/campaign-finance-data/technical-specifications/

## API vs Bulk Data (Current Scope)

- FEC bulk data provides downloadable files (CSV/ZIP) suitable for repeatable batch ETL.
- The FEC API provides endpoint-based access for filtered, on-demand retrieval and app integrations.
- This repository currently uses bulk downloads only.
- The FEC API is documented here for future use, but API ingestion is not currently part of this ETL setup.

## Storage Approach (Current Scope)

- Parquet is not required for this project.
- Source ZIP files are downloaded and managed in `data/raw/`.
- DuckDB reads source text/CSV data from extracted files and stores modeled results in the `.duckdb` database file.

## Stack

- DuckDB for local analytics database and SQL transforms
- curl for bulk data downloads
- PowerShell scripts for repeatable ETL jobs
- Windows host (PowerShell 7+ recommended)

## Project Structure

```text
fec-data/
  .config/
    configuration.winget  # winget tool provisioning (Microsoft-recommended location)
  data/
    raw/         # Downloaded source files (zip/csv/json)
    staging/     # Unpacked and lightly normalized files
    processed/   # Curated extracts and export-ready data
  db/
    fec.duckdb   # Main DuckDB database file (created at runtime)
  scripts/
    fetch/       # curl download scripts
    transform/   # preprocessing scripts (PowerShell)
    load/        # duckdb load scripts and orchestration
  sql/
    schema/      # CREATE TABLE / DDL files
    transform/   # INSERT...SELECT / merge / cleanup SQL
    analysis/    # QA checks and ad hoc queries
  logs/          # ETL run logs
  tmp/           # Temporary work artifacts
```

Note: `data/`, local `db/` artifacts, `logs/`, and `tmp/` are intended for local runtime files and are git-ignored via `.gitignore` (folder placeholders are kept with `.gitkeep`).

## Prerequisites (Windows)

Install:

1. DuckDB CLI
2. curl
3. PowerShell 7+

Verify tools:

```powershell
duckdb --version
curl --version
$PSVersionTable.PSVersion
```

### Optional: Provision or Update Tools with winget configure

This repository includes a Windows package provisioning file at `.config/configuration.winget` (the [Microsoft-recommended naming convention](https://learn.microsoft.com/en-us/windows/package-manager/configuration/create#file-naming-convention)).

Run from project root:

```powershell
.\scripts\setup-tools.ps1
```

This script is **run manually by choice** — it is never called automatically by the ETL pipeline. It is safe to rerun at any time: `winget configure` is idempotent and will install missing tools or upgrade existing ones to the configured version.

The configuration installs:

- DuckDB CLI (`DuckDB.cli`)
- curl (`cURL.cURL`)
- jq (`jqlang.jq`)

## Quick Start

1. Create the DuckDB file:

```powershell
duckdb db/fec.duckdb ".databases"
```

2. Add schema SQL files in `sql/schema/`.

3. Add a fetch script in `scripts/fetch/` (example command pattern):

```powershell
curl -L "https://www.fec.gov/files/bulk-downloads/2024/indiv24.zip" -o data/raw/indiv24.zip
```

For the FEC bulk downloader in PowerShell, which caches the raw ZIP artifacts for DuckDB to read directly:

```powershell
.\scripts\fetch\fetch_bulk.ps1 2020
```

4. Load and transform with DuckDB:

```powershell
duckdb db/fec.duckdb -c ".read sql/schema/001_base_tables.sql"
duckdb db/fec.duckdb -c ".read sql/transform/010_load_individual_contributions.sql"
```

## Recommended Conventions

- Keep raw source files immutable in `data/raw/`.
- Manage and track downloaded ZIP files in `data/raw/`.
- Write all transformations as SQL in `sql/transform/` when possible.
- Use PowerShell for all project scripting and orchestration.
- Name SQL files with numeric prefixes for deterministic order:
  - `001_...sql`, `010_...sql`, `020_...sql`
- Keep scripts idempotent so reruns are safe.
- Log all pipeline runs to `logs/`.

## Next Steps

- Add the first source-specific downloader in `scripts/fetch/`.
- Define base tables in `sql/schema/`.
- Add one end-to-end PowerShell run script that calls fetch, then load, then QA checks.
