# Project Memory

This file captures project-specific lessons learned so they are versioned with the repository.

## ETL and PowerShell Notes

- In PowerShell strings, use `${Var}:` when a variable is immediately followed by a colon to avoid parser errors.
- Keep ETL scripts year-first for this repo: `data/{cycle}/raw` for cached ZIP landing.
- Use module entrypoints in scripts to avoid duplicated retrieve/transform/load logic.
- For external CLI calls in verbose mode, stream stdout/stderr via `2>&1 | ForEach-Object { Write-Verbose ... }` to show runtime progress without changing normal output.

## DuckDB ZIP Loading Notes

- The Python loader extracts each required ZIP entry to `tmp/load-fec/` before `read_csv`, so DuckDB `zipfs` is no longer required for raw loads.
- Keep explicit table-to-entry ZIP mapping (for example, `ccl -> ccl.txt`, `indiv -> itcont.txt`) to avoid ambiguity, especially for multi-file archives like `indiv`.

## Metadata Modeling Decision

- Raw FEC tables are full-refresh payload tables; row-level load metadata columns are intentionally omitted.
- Load provenance is tracked centrally in `etl.load_history` (one row per table load operation).
