# Copilot Instructions — FEC Campaign Finance ETL

<!-- Analyzer note: This is a pure ETL project. There is no build system, no package manager (npm/pip/maven/gradle), no test runner, and no lint pipeline. The only task runners are PowerShell scripts and DuckDB CLI invoked directly. Do not apply heuristics for software build/test/lint toolchains. -->

## Project Summary

This is a batch ETL project that downloads Federal Election Commission (FEC) bulk ZIP files, manages them locally, and loads them into a local DuckDB database for analysis. The host OS is Windows. All scripting is done in PowerShell.

## Stack

- DuckDB CLI — local analytics database and SQL transforms
- curl — bulk file downloads
- 7-Zip CLI — unpacking downloaded zip files
- PowerShell — ETL orchestration scripts
- jq — JSON parsing in shell pipelines
- Windows (PowerShell for ETL and admin tasks)
- winget — tool provisioning (`.config/configuration.winget`)

## Storage Strategy

- Parquet is not required for this project.
- ZIP files are downloaded to `data/raw/` and managed as immutable source artifacts.
- DuckDB imports source records from extracted files and persists modeled data in native DuckDB storage (`.duckdb`).

## Key FEC Data Sources

- Bulk data portal: https://www.fec.gov/data/browse-data/?tab=bulk-data
- Electronic filing specs: https://www.fec.gov/campaign-finance-data/technical-specifications/
- FEC API (not currently used — documented for future reference only): https://api.open.fec.gov/developers/

## Repository Layout

```
.config/                   # winget provisioning (Microsoft-recommended location)
  configuration.winget     # winget configure file
data/raw/                  # Downloaded source files — git-ignored, not committed
data/staging/              # Unpacked/normalized files — git-ignored
data/processed/            # Curated extracts — git-ignored
db/                        # DuckDB .duckdb files — git-ignored
scripts/fetch/             # curl download scripts
scripts/transform/         # PowerShell preprocessing
scripts/load/              # DuckDB load/orchestration scripts
sql/schema/                # DDL: CREATE TABLE statements
sql/transform/             # INSERT-SELECT / merge / cleanup SQL
sql/analysis/              # QA checks and ad hoc queries
artifacts/exploration/     # HTML: approach comparisons, implementation plans — committed
artifacts/diagrams/        # HTML: data flow diagrams, schema maps — committed
artifacts/reviews/         # HTML: annotated SQL/script reviews — committed
artifacts/analysis/        # HTML: interactive query results, explainers — committed
artifacts/reports/         # HTML: per-run ETL reports — git-ignored
logs/                      # ETL run logs — git-ignored
tmp/                       # Temp artifacts — git-ignored
```

## Setting Up Tools (run once on a new machine)

Run the provisioning script from the project root:
```powershell
.\scripts\setup-tools.ps1
```

This calls `winget configure` against `.config/configuration.winget` and installs DuckDB CLI, Git, curl, and jq.

## Common Commands

Create the DuckDB database:
```powershell
duckdb db/fec.duckdb ".databases"
```

Download a bulk file:
```powershell
curl -L "https://www.fec.gov/files/bulk-downloads/2024/indiv24.zip" -o data/raw/indiv24.zip
```

Apply schema or transform SQL:
```powershell
duckdb db/fec.duckdb -c ".read sql/schema/001_base_tables.sql"
duckdb db/fec.duckdb -c ".read sql/transform/010_load_individual_contributions.sql"
```

## Conventions

1. `data/`, `db/`, `logs/`, `tmp/` are local runtime directories — never commit data files.
2. SQL files use numeric prefixes for deterministic execution order: `001_`, `010_`, `020_`, etc.
3. All scripts must be idempotent (safe to rerun).
4. Raw source files in `data/raw/` are immutable — transformations happen downstream.
5. Use SQL in `sql/transform/` for data shaping logic; use PowerShell when SQL is insufficient (e.g., file downloads, unpacking, renaming).
6. Log ETL runs to `logs/` with timestamps.
7. On ETL errors (failed downloads, SQL execution failures), log the error to `logs/` with a timestamp and exit with a non-zero status. Do not silently continue past a failed step.

## HTML Artifacts (Living Documents)

When a response would require multiple sections of markdown prose (roughly 300+ words, or requiring headers to organize), generate a self-contained `.html` file instead of markdown. Single-answer or short code responses remain as markdown. These are opened directly in a browser — no build step.

- Save to the appropriate `artifacts/` subdirectory
- Files must be fully self-contained (no external dependencies)
- Always end with: "Output this as a single self-contained `.html` file I can open in a browser. No external dependencies."

| Use case | Directory |
|---|---|
| Approach comparisons, implementation plans | `artifacts/exploration/` |
| ETL pipeline diagrams, schema maps | `artifacts/diagrams/` |
| Annotated SQL/script reviews | `artifacts/reviews/` |
| Format explainers, concept walkthroughs | `artifacts/analysis/` |
| Per-run pipeline reports (row counts, timing) | `artifacts/reports/` (not committed) |

## Agent Instructions Update

- **Browsing FEC Data**: The FEC provides an interactive data browsing interface at [FEC Browse Data](https://www.fec.gov/data/browse-data). This should be referenced early in any HTML file summarizing FEC data sources.
- **Importing FEC Data in ETL Projects**: Ensure that the hierarchical organization of the FEC data is reflected in ETL workflows. This includes maintaining consistency with the structure of the FEC browse data page.

## Out of Scope (Current)

- FEC API ingestion (documented but not implemented)
- Scheduled/automated runs (manual execution only for now)
- Node.js / npm — this project has no JavaScript dependencies or build tooling