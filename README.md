# MoneyTrail - Follow the money in politics

“Follow the money.” — Deep Thraot in All the President’s Men

MoneyTrail is a citizen‑developer project for loading the Federal Election Commission’s bulk data files into a personal OLAP database. Once the data is structured and queryable, it can be used to conduct independent research into who is contributing and spending money in federal elections, and how financial activity shapes our political environment.

Instead of relying on what political actors say, MoneyTrail makes it possible to observe what they actually do through their financial disclosures.

Scope note: this setup is currently optimized for single-user local operation.
Operational metadata and QA logs are stored in a local, single-user SQLite database.

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

## HTML Artifact Preview

This repo keeps committed, self-contained HTML artifacts under `artifacts/` for analysis notes, diagrams, reviews, and reports. For this project, the recommended in-editor preview workflow is the official VS Code Live Preview extension (`ms-vscode.live-server`), which is listed in the workspace recommendations.

1. Open an HTML artifact file.
2. Run `Live Preview: Show Preview` from the Command Palette.
3. Keep the preview beside the editor while you iterate on the file.

For a final rendering check, open the same file in your normal browser as well.

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

- Load all configured raw models for one cycle via dbt zipfs:

```powershell
uv run load --cycle 2026
```

- Load one or more tables only:

```powershell
uv run load --cycle 2026 --tables cm cn
```

- Override dbt thread count for the loader:

```powershell
uv run load --cycle 2026 --tables indiv oppexp oth pas2 --dbt-threads 1
```

- Pass through additional dbt selectors if needed:

```powershell
uv run load --cycle 2026 --select state:modified+
```

- Use a custom dbt profiles directory:

```powershell
uv run load --cycle 2026 --profiles-dir .
```

- Note: loader execution now uses the dbt zipfs path rather than Python ZIP extraction.

### Benchmark (`uv run benchmark-load`)

- Benchmark dbt zipfs load performance for one cycle:

```powershell
uv run benchmark-load --cycle 2026
```

- Benchmark specific tables only:

```powershell
uv run benchmark-load --cycle 2026 --tables indiv oppexp oth pas2
```

- Add a warm-up pass before the measured run:

```powershell
uv run benchmark-load --cycle 2026 --warmup
```

- Override thread count used by benchmark runs:

```powershell
uv run benchmark-load --cycle 2026 --tables indiv oppexp oth pas2 --dbt-threads 1
```

- Keep isolated benchmark databases and logs for inspection:

```powershell
uv run benchmark-load --cycle 2026 --keep-run-dir
```

- The command writes CSV results under `logs/load-timing/` and stores per-run artifacts under `tmp/benchmark-load/`.
- The benchmark defaults to `--dbt-threads 1` for large-fact stability and repeatability.

### Legacy Note

- The previous Python extract-based loader path is no longer used as the default `load` command.
- The repository now standardizes on the dbt zipfs path for raw table loads.

### Common Recovery Steps

```powershell
uv sync
uv run download --cycles 2026 --force
uv run load --cycle 2026 --dbt-threads 1
```
