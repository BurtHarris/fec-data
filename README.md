# MoneyTrail - Follow the money in politics

“Follow the money.” — Deep Thraot in All the President’s Men

MoneyTrail is a citizen‑developer project for loading the Federal Election Commission’s bulk data files into a personal OLAP database. Once the data is structured and queryable, it can be used to conduct independent research into who is contributing and spending money in federal elections, and how financial activity shapes our political environment.

Instead of relying on what political actors say, MoneyTrail makes it possible to observe what they actually do through their financial disclosures.

Scope note: this setup is currently optimized for single-user local operation. The operations web app UI has been downscoped to a read-only Monitoring & Health Dashboard — exposing only the /health and /history screens. Interactive run submission and other operational routes have been disabled (commented out) to prioritize a low-maintenance, read-only status page.

Download metadata and dashboard progress live in a SQLite database configured in `config/data_scope.yml`. Command audit logs remain in the local SQLite `db/ops_web.sqlite` store.

### Worktree & Branching

For local development, prefer using Git worktrees to isolate features and experiments. Create a new worktree per branch (for example: `git worktree add ..\wt-<branch> <branch>`) so working directories remain independent from the main worktree. Use short, descriptive branch names (e.g., `feat/add-indiv-loader`, `fix/bench-crash`, `docs/update-readme`) and base feature branches on `main`. Open pull requests for review and keep worktrees short-lived; when work is complete, merge or rebase as appropriate and remove the worktree with `git worktree remove ..\wt-<branch>`.

Commit messages should be clear and prefixed by type (e.g., `feat:`, `fix:`, `docs:`, `chore:`). Never commit large data or runtime artifacts — `data/`, `db/`, `logs/`, and `tmp/` are ignored. Keep worktree directories outside those runtime paths to avoid accidental commits of generated data.

Developer notes: [docs/matt-pocock-skills.md](docs/matt-pocock-skills.md)

## Simple Start

Run from repository root:

1. Review/edit `config/data_scope.yml` for the cycles/tables you want.
2. Set `metadata_database.sqlite.path` in `config/data_scope.yml` to the SQLite database that should hold download tracking and dashboard status.
3. Run:

```powershell
uv sync
uv run download --cycles 2026
uv run load --cycle 2026
```

That is the default workflow.

## What You Get

- ZIP files cached under `data/<cycle>/`
- Download progress per cycle/table pair in the operations dashboard
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
- SQLite (for download metadata and dashboard progress)

Optional tool bootstrap on Windows:

```powershell
./scripts/setup-tools.ps1
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

### Dev Cycle Shortcuts (PowerShell)

For quick local iteration, this repo includes two lightweight wrapper scripts under `scripts/`:

```powershell
# Start/restart the local ops dashboard and open the browser.
# (Stops the previous server instance if needed.)
.\scripts\web.ps1

# Fetch/download using the current config in config/data_scope.yml.
.\scripts\etl.ps1 fetch

# Load using the current config (defaults to the latest facts cycle).
.\scripts\etl.ps1 load

# Or specify a cycle explicitly.
.\scripts\etl.ps1 load -Cycle 2026
```

Use `-NoSync` if you already ran `uv sync` and want to skip dependency resolution.

### Operations Web App (Local Shell)

Run the internal operations web app shell in local-trusted mode:

```powershell
uv sync
uv run ops-web
```

Open `http://127.0.0.1:8787` in your browser. The app binds to localhost by default.

Optional development flags:

```powershell
uv run ops-web --reload
uv run ops-web --host 127.0.0.1 --port 8787
```

Health check endpoint:

```powershell
curl http://127.0.0.1:8787/healthz
```

Run submission endpoint (allowlisted commands only):

```powershell
curl -X POST "http://127.0.0.1:8787/api/runs/submit" \
	-H "Content-Type: application/json" \
	-d '{"command":"fetch","operator_id":"local-operator","armed":true,"confirmed":true,"cycle":2026,"tables":["cm"],"force":false}'
```

Admission gates:

- Only `fetch`, `load`, and `benchmark-load` are allowlisted.
- Requests are rejected unless `armed=true` and `confirmed=true`.
- Admission and launch outcomes are persisted to `db/ops_web.sqlite` (`command_run_log`).
- Process output is written to `logs/ops-web/`.

Run lock and lifecycle endpoints:

```powershell
curl "http://127.0.0.1:8787/api/runs/active"
curl "http://127.0.0.1:8787/api/runs/<request_id>"
curl -X POST "http://127.0.0.1:8787/api/runs/<request_id>/cancel"
```

Lifecycle states include `running`, `completed`, `failed`, `canceled`, and `rejected`.
Only one workflow run can be active at a time; lock contention is persisted as a rejected run attempt.

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
