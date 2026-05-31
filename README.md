# MoneyTrail - Follow the money in politics

“Follow the money.” — Deep Thraot in All the President’s Men

MoneyTrail is a citizen‑developer project for loading the Federal Election Commission’s bulk data files into a personal OLAP database. Once the data is structured and queryable, it can be used to conduct independent research into who is contributing and spending money in federal elections, and how financial activity shapes our political environment.

Instead of relying on what political actors say, MoneyTrail makes it possible to observe what they actually do through their financial disclosures.

Scope note: this setup is currently optimized for single-user local operation.
Operational metadata and QA logs are stored in a local, single-user SQLite database.

## Simple Start

Run from repository root:

1. Review/edit `config/fec_bulk_coverage.yml` for the cycles/tables you want.
2. Run:

```powershell
uv sync
uv run download --cycles 2026
uv run load --cycle 2026
```

That is the default workflow.

## What You Get

- ZIP files cached under `data/<cycle>/`
- Raw tables in DuckDB such as `raw_fec.cm_2026`
- Benchmark outputs in `logs/load-timing/`

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

When opening HTML artifacts in this project, prefer the rendered view over raw source whenever practical.

Option A: Built-in browser rendering (Live Preview)
1. Open an HTML artifact file.
2. Run `Live Preview: Show Preview` from the Command Palette.
3. Keep the preview beside the editor while you iterate on the file.

Option B: Visual editor workflow (WYSIWYG HTML Editor)
1. Open an HTML file.
2. Run `WYSIWYG HTML: Open WYSIWYG Editor` from the Command Palette.
3. Edit in visual mode with bidirectional sync back to source.

For a final rendering check, open the same file in your normal browser as well.

Validate HTML links (local + remote):

```powershell
.\scripts\check-html-links.ps1
```

This writes a JSON report to `tmp/html_link_check_artifacts.json` and exits non-zero if broken links are found.

## CLI Commands

The repository now standardizes on the dbt `zipfs` loader path.

### Performance Benchmark (Kept for Future Tests)

```powershell
uv run benchmark-load --cycle 2026 --tables indiv oppexp oth pas2 --warmup --dbt-threads 1
```

This writes CSV results to `logs/load-timing/` and run artifacts to `tmp/benchmark-load/`.

### Common Recovery

```powershell
uv sync
uv run download --cycles 2026 --force
uv run load --cycle 2026 --dbt-threads 1
```

For all advanced flags, use:

```powershell
uv run load --help
uv run benchmark-load --help
```
