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

## Suggested Project Structure

```text
fec-data/
  data/
    raw/         # Downloaded source files (zip/csv/json)
    staging/     # Unpacked and lightly normalized files
    processed/   # Curated extracts and export-ready data
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

## Quick Start

1. Create the DuckDB file:

```bash
duckdb db/fec.duckdb ".databases"
```

2. Add schema SQL files in `sql/schema/`.

3. Add a fetch script in `scripts/fetch/` (example command pattern):

```bash
curl -L "https://www.fec.gov/files/bulk-downloads/2024/indiv24.zip" -o data/raw/indiv24.zip
```

4. Load and transform with DuckDB:

```bash
duckdb db/fec.duckdb -c ".read sql/schema/001_base_tables.sql"
duckdb db/fec.duckdb -c ".read sql/transform/010_load_individual_contributions.sql"
```

## Recommended Conventions

- Keep raw source files immutable in `data/raw/`.
- Write all transformations as SQL in `sql/transform/` when possible.
- Name SQL files with numeric prefixes for deterministic order:
  - `001_...sql`, `010_...sql`, `020_...sql`
- Keep scripts idempotent so reruns are safe.
- Log all pipeline runs to `logs/`.

## Next Steps

- Add the first source-specific downloader in `scripts/fetch/`.
- Define base tables in `sql/schema/`.
- Add one end-to-end run script that calls fetch, then load, then QA checks.
