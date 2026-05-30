# FEC Campaign Finance ETL (Simple Usage)

This project downloads FEC bulk ZIPs and loads them into DuckDB.

Scope note: this setup is currently optimized for single-user local operation.
Operational metadata and QA logs are stored in a local SQLite database.

If you just want to run it:

1. Review/edit the YAML config
2. Download files
3. Load DuckDB tables

## Simple Start

Run from repository root:

1. Review/edit `config/fec_bulk_coverage.yml` for the cycles/tables you want.

2. Run:

```powershell
uv sync
uv run download --cycles 2026
uv run load
```

That is the default workflow.

## What You Get

- ZIP files cached under `data/<cycle>/`
- Raw tables in DuckDB such as `raw_fec.cm_2026`
- Load metadata and QA logs in `db/fec-metadata.sqlite`

Quick check:

```powershell
duckdb db/fec.duckdb "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema='raw_fec' ORDER BY table_name;"
```

## Prerequisites

- Python 3.11+
- `uv`
- DuckDB CLI (optional, but useful for inspection)
- SQLite (uses Python built-in `sqlite3`; no separate install required)

Optional tool bootstrap on Windows:

```powershell
.\scripts\setup-tools.ps1
```

## Appendix: CLI Debug Options

Use these only when diagnosing issues.

### Downloader (`uv run download`)

- Single cycle:

```powershell
uv run download --cycles 2026
```

- Specific tables only:

```powershell
uv run download --cycles 2026 --tables cm cn indiv
```

- Force refresh:

```powershell
uv run download --cycles 2026 --force
```

- Lower concurrency to reduce network pressure:

```powershell
uv run download --cycles 2026 --parallelism 1
```

- More frequent progress output:

```powershell
uv run download --cycles 2026 --progress-interval 1.0
```

- Enforce configured coverage when debugging unusual cycle selections:

```powershell
uv run download --cycles 2030 --strict-coverage
```

### Loader (`uv run load`)

- Infer cycles and tables from downloaded ZIPs:

```powershell
uv run load
```

- Load all configured tables for one explicit cycle:

```powershell
uv run load --cycle 2026
```

- Load one or more tables only:

```powershell
uv run load --cycle 2026 --tables cm cn
```

- Force reload even if source ZIP hash is unchanged:

```powershell
uv run load --cycle 2026 --tables cm --force
```

- Use a different database file for repro/debug:

```powershell
uv run load --cycle 2026 --db-path db/fec-debug.duckdb
```

- Use a different metadata DB file for repro/debug:

```powershell
uv run load --cycle 2026 --metadata-db-path db/fec-metadata-debug.sqlite
```

### Common Recovery Steps

```powershell
uv sync
uv run download --cycles 2026 --force
uv run load --cycle 2026 --force
```
