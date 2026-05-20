# Lessons Learned

## Medallion Architecture

This project follows the **medallion architecture** pattern (also called multi-hop or bronze-silver-gold):
- **Bronze**: Raw downloaded FEC bulk data archives (ZIP files)
- **Silver**: Extracted and lightly normalized files (CSV tables from ZIP archives)
- **Gold**: Curated and refined tables ready for analysis

For background, see [Databricks' medallion architecture documentation](https://www.databricks.com/blog/2022/06/24/use-the-medallion-multi-hop-architecture-to-build-data-lakehouses-in-databricks.html).

## CN Table Slice

- Start each cycle with a checkpoint: if there are no tracked changes, continue without forcing a no-op commit.
- Keep ETL SQL file naming ordered (`001_`, `020_`, `030_`) so load execution order remains deterministic.
- Reusing the cm snapshot pattern for cn worked with only file/table name changes and produced a cycle baseline quickly.
- Current transform wrapper extracts all zips in the cycle source folder; running a single-file update can still trigger multi-file extraction.
- Verified 2024 cn baseline load with `row_count = 9805` from `data\\2024\\silver\\cn.txt`.

## CCL Table Slice

- The same snapshot pattern used for `cm` and `cn` also worked for `ccl` with only table and file name substitutions.
- Verified 2024 ccl baseline load with `row_count = 8623` from `data\\2024\\silver\\ccl.txt`.
- Running the transform step still expands all archives in the cycle silver source; this is acceptable for now but should become selective when incremental phases begin.

## Remaining Non-Indiv Slice (weball, oppexp, pas2, oth)

- Implemented these four families without extraction by baselining from bronze zip presence (`data/{cycle}/bronze/*.zip`) instead of silver row counts.
- Stored `row_count` as `NULL` intentionally for this phase; these tables currently track cycle availability and source artifact paths.
- `glob(...)` + regex against normalized file paths is stable; simplified regex patterns were required for consistent cycle extraction in DuckDB.
- Verified successful baseline insertion for cycles 2020 and 2024 across all four families.

## Indiv Table Slice

- `indiv` is large enough that a bronze-zip baseline is the safest first implementation step.
- Implemented cycle/source tracking with `row_count = NULL` and `load_mode = raw-zip-baseline` to keep progress explicit while avoiding heavyweight full scans.
- Verified snapshot entries for cycles 2020 and 2024 from raw zip presence; this sets up a clean handoff to a future incremental counting phase.

## Terminology Standardization (Commit: 10a53ff)

- Adopted medallion architecture terminology consistently across the codebase:
  - **raw** → **bronze** (landing zone for downloaded files)
  - **staging** → **silver** (zone for extracted/unpacked files)
  - **processed** → **gold** (zone for curated/refined tables)
- Updated all 21 files: PowerShell modules, wrapper scripts, SQL transforms, documentation, and artifacts.
- Added reference to [Databricks medallion architecture guide](https://www.databricks.com/blog/2022/06/24/use-the-medallion-multi-hop-architecture-to-build-data-lakehouses-in-databricks.html) in project documentation.
- All parameter defaults and path patterns now use bronze/silver/gold naming for consistency.
- This terminology aligns with industry standards and improves clarity for future collaborators.
