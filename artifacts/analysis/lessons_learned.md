# Lessons Learned

## CN Table Slice

- Start each cycle with a checkpoint: if there are no tracked changes, continue without forcing a no-op commit.
- Keep ETL SQL file naming ordered (`001_`, `020_`, `030_`) so load execution order remains deterministic.
- Reusing the cm snapshot pattern for cn worked with only file/table name changes and produced a cycle baseline quickly.
- Current transform wrapper extracts all zips in the cycle source folder; running a single-file update can still trigger multi-file extraction.
- Verified 2024 cn baseline load with `row_count = 9805` from `data\\2024\\staging\\cn.txt`.

## CCL Table Slice

- The same snapshot pattern used for `cm` and `cn` also worked for `ccl` with only table and file name substitutions.
- Verified 2024 ccl baseline load with `row_count = 8623` from `data\\2024\\staging\\ccl.txt`.
- Running the transform step still expands all archives in the cycle staging source; this is acceptable for now but should become selective when incremental phases begin.

## Remaining Non-Indiv Slice (weball, oppexp, pas2, oth)

- Implemented these four families without extraction by baselining from raw zip presence (`data/{cycle}/raw/*.zip`) instead of staging row counts.
- Stored `row_count` as `NULL` intentionally for this phase; these tables currently track cycle availability and source artifact paths.
- `glob(...)` + regex against normalized file paths is stable; simplified regex patterns were required for consistent cycle extraction in DuckDB.
- Verified successful baseline insertion for cycles 2020 and 2024 across all four families.
