# FEC Campaign Finance ETL (DuckDB + curl + bash on Windows)

This repository is set up for an ETL workflow that downloads Federal Election Commission (FEC) campaign finance data, stages it, and loads modeled tables into DuckDB.

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

## Stack

- DuckDB for local analytics database and SQL transforms
- curl for bulk data downloads
- bash scripts for repeatable ETL jobs
- Windows host (Git Bash or WSL recommended for bash scripts)

## Project Structure

```text
fec-data/
  .config/
    configuration.winget  # winget tool provisioning (Microsoft-recommended location)
  data/
    bronze/      # Downloaded source files (zip/csv/json)
    silver/      # Unpacked and lightly normalized files
    gold/        # Curated extracts and export-ready data
  db/
    fec.duckdb   # Main DuckDB database file (created at runtime)
  scripts/
    fetch/       # curl download scripts
    transform/   # preprocessing scripts (bash + optional awk/sed)
    load/        # duckdb load scripts and orchestration
  sql/
    schema/      # CREATE TABLE / DDL files
    transform/   # INSERT...SELECT / merge / cleanup SQL
    analysis/    # QA checks and ad hoc queries
  logs/          # ETL run logs
  tmp/           # Temporary work artifacts
```

Note: `data/`, local `db/` artifacts, `logs/`, and `tmp/` are intended for local runtime files and are git-ignored via `.gitignore` (folder placeholders are kept with `.gitkeep`).

This project uses the **medallion architecture** pattern:
- **Bronze** (raw ingestion): Downloaded FEC bulk data files (ZIP archives)
- **Silver** (cleaned/standardized): Extracted and lightly normalized files
- **Gold** (analytics-ready): Curated tables and refined extracts

For more on medallion architecture, see [Databricks' medallion architecture documentation](https://www.databricks.com/blog/2022/06/24/use-the-medallion-multi-hop-architecture-to-build-data-lakehouses-in-databricks.html).

## Prerequisites (Windows)

Install:

1. DuckDB CLI
2. curl
3. A bash environment:
   - Git Bash, or
   - WSL (Ubuntu)

Verify tools:

```bash
duckdb --version
curl --version
bash --version
```

If PowerShell resolves `bash` to WSL on your machine, use the bundled PowerShell wrapper to force Git Bash for fetch jobs:

```powershell
.\scripts\fetch\fetch_bulk.ps1 2020
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
- Git for Windows / Git Bash (`Git.Git`)
- WSL (`Microsoft.WSL`) as an optional bash environment
- curl (`cURL.cURL`)
- jq (`jqlang.jq`)

## Quick Start

1. Create the DuckDB file:

```bash
duckdb db/fec.duckdb ".databases"
```

2. Add schema SQL files in `sql/schema/`.

3. Add a fetch script in `scripts/fetch/` (example command pattern):

```bash
curl -L "https://www.fec.gov/files/bulk-downloads/2024/indiv24.zip" -o data/bronze/indiv24.zip
```

For the existing FEC bulk downloader on Windows PowerShell:

```powershell
.\scripts\fetch\fetch_bulk.ps1 2020
```

4. Extract and transform with DuckDB:

```bash
duckdb db/fec.duckdb -c ".read sql/schema/001_etl_base.sql"
duckdb db/fec.duckdb -c ".read sql/transform/020_load_cm_snapshot.sql"
```

## Recommended Conventions

- Keep bronze source files immutable in `data/bronze/`.
- Extract to silver: `data/silver/`.
- Load to gold: tables in DuckDB via `sql/transform/`.
- Write all transformations as SQL in `sql/transform/` when possible.
- Name SQL files with numeric prefixes for deterministic order:
  - `001_...sql`, `010_...sql`, `020_...sql`
- Keep scripts idempotent so reruns are safe.
- Log all pipeline runs to `logs/`.

## Next Steps

- Add the first source-specific downloader in `scripts/fetch/`.
- Define base tables in `sql/schema/`.
- Add one end-to-end run script that calls fetch, then load, then QA checks.
