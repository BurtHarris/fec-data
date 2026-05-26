# Project Memory

This file captures project-specific lessons learned so they are versioned with the repository.

## ETL and PowerShell Notes

- In PowerShell strings, use `${Var}:` when a variable is immediately followed by a colon to avoid parser errors.
- Keep ETL scripts year-first for this repo: `data/{cycle}/raw` for cached ZIP landing.
- Use module entrypoints in scripts to avoid duplicated retrieve/transform/load logic.
- For external CLI calls in verbose mode, stream stdout/stderr via `2>&1 | ForEach-Object { Write-Verbose ... }` to show runtime progress without changing normal output.

## DuckDB ZIP Loading Notes

- DuckDB ZIP entry reads in this repo require the `zipfs` community extension (`INSTALL zipfs FROM community;` then `LOAD zipfs;`) before using `zip://` URIs.
- Use canonical zipfs paths with forward slashes: `zip://E:/.../archive.zip/entry.txt`.
- Keep explicit table-to-entry ZIP mapping (for example, `ccl -> ccl.txt`, `indiv -> itcont.txt`) to avoid ambiguity, especially for multi-file archives like `indiv`.
