# Copilot Workflow Tips for dbt ZipFS FEC ETL

This repository now standardizes on the dbt ZipFS load path. These tips focus on what is still useful after that migration.

## 1) Use the current command trio only

Prefer the supported workflow and avoid legacy script-oriented guidance:

1. `uv run download --cycles 2026`
2. `uv run load --cycle 2026 --dbt-threads 1`
3. `uv run benchmark-load --cycle 2026 --tables indiv oppexp oth pas2 --warmup --dbt-threads 1`

## 2) Keep dbt threading conservative for large fact tables

For `indiv`, `oppexp`, `oth`, and `pas2`, use `--dbt-threads 1` unless you are explicitly testing concurrency. Serial threading is the safer default for local memory pressure.

## 3) Scope runs intentionally

Use `--tables` for focused benchmarks and partial loads. Use `--select` only when you need dbt selector behavior beyond table-name selection.

## 4) Treat logs and timing CSVs as the source of truth

After each run, inspect artifacts before drawing conclusions:

1. Timing results in `logs/load-timing/benchmark_load_<cycle>_<label>.csv`
2. Isolated benchmark artifacts in `tmp/benchmark-load/<cycle>-<label>/`
3. dbt logs/run metadata in each benchmark run directory

## 5) Ask Copilot for artifact analysis, not orchestration tricks

The biggest value now is post-run analysis. Good prompt pattern:

`Compare the two newest benchmark_load CSV files, summarize total runtime delta, fact-table subtotal delta, and flag any table with missing row_count.`

