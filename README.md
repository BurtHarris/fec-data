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
    setup-tools.ps1
    enable-fec-data-scripts.ps1
    fetch-bulk.ps1
    extract-zips.ps1
    probe-fec-2026.ps1
    generate-diagram.ps1
  sql/
    schema/      # CREATE TABLE / DDL files
    transform/   # INSERT...SELECT / merge / cleanup SQL
    qa/          # QA checks and ad hoc queries
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

### Option A: dbt + DuckDB workflow

This is the recommended migration path away from PowerShell orchestration. The
Python downloader caches source ZIPs, and dbt builds DuckDB tables from those
ZIPs.

1. Install the Python/dbt environment:

```powershell
uv sync
```

2. Download according to the configured coverage ranges:

```powershell
uv run download
```

You can override the defaults for debugging:

```powershell
uv run download --cycles 2026 --tables cm cn --parallelism 2
```

Coverage can also be configured by cycle type in `config/fec_bulk_coverage.yml`.
When no explicit tables are provided, the downloader resolves tables from that
config.

```powershell
uv run download --cycles 2024
```

To fail fast for cycles not listed in the coverage config, use strict mode:

```powershell
uv run download --cycles 2030 --strict-coverage
```

3. Build DuckDB tables with dbt:

```powershell
uv run dbt run --profiles-dir . --vars "{cycle: 2026}"
```

4. Run the starter dbt tests:

```powershell
uv run dbt test --profiles-dir . --vars "{cycle: 2026}"
```

The dbt models live in `models/raw_fec/`. Each model reads one FEC ZIP entry and
materializes a table such as `raw_fec.cm_2026` in `db/fec.duckdb`.

### Review Notes for Known Data Issues

Human investigation notes live in the `review` schema. Use these tables when a
test failure or unusual report needs context that should survive reloads:

- `review.issue` stores the main issue or anomaly.
- `review.issue_relationship` links broad findings to narrower explanations.
- `review.issue_entity` attaches committees, candidates, transactions, columns,
  and rows to an issue.
- `review.issue_evidence` stores query results, analyst notes, and source links.
- `review.issue_decision` records why an issue was accepted, reopened, or closed.
- `review.issue_metric` keeps measured counts and amounts for comparison over time.

Load the starter review records with:

```powershell
uv run dbt seed --profiles-dir . --select review --full-refresh
```

For example, the broad `pas2.CAND_ID` null warning is linked to a narrower
`MENENDEZ FOR CONGRESS` duplicate-candidate-ID investigation.

### Option B: legacy PowerShell workflow

1. Create the DuckDB file:

```powershell
duckdb db/fec.duckdb ".databases"
```

2. Add schema SQL files in `sql/schema/`.

3. Add a fetch script in `scripts/` (example command pattern):

```powershell
curl -L "https://www.fec.gov/files/bulk-downloads/2024/indiv24.zip" -o data/raw/indiv24.zip
```

For the FEC bulk downloader in PowerShell, which caches the raw ZIP artifacts for DuckDB to read directly:

```powershell
.\scripts\fetch-bulk.ps1 2020
```

To make the repo scripts callable by name from terminal, add the repo `scripts` folder to your PowerShell PATH:

```powershell
.\scripts\enable-fec-data-scripts.ps1 -Persist
```

That appends the repo `scripts` directory to your PowerShell profile PATH.

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
- Track load provenance in `etl.load_history`; keep raw load tables payload-only.

## Project Memory

- Repository-specific lessons learned and implementation notes are tracked in `PROJECT_MEMORY.md`.

## Next Steps

- Add the first source-specific downloader in `scripts/`.
- Define base tables in `sql/schema/`.
- Add one end-to-end PowerShell run script that calls fetch, then load, then QA checks.
