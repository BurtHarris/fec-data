# Lessons Learned

## CN Table Slice

- Start each cycle with a checkpoint: if there are no tracked changes, continue without forcing a no-op commit.
- Keep ETL SQL file naming ordered (`001_`, `020_`, `030_`) so load execution order remains deterministic.
- Reusing the cm snapshot pattern for cn worked with only file/table name changes and produced a cycle baseline quickly.
- Current transform wrapper extracts all zips in the cycle source folder; running a single-file update can still trigger multi-file extraction.
- Verified 2024 cn baseline load with `row_count = 9805` from `data\\2024\\staging\\cn.txt`.
