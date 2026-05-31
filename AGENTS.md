# Agent Notes

## ZIP Load Strategy

- Prefer the dbt `zipfs` path for large fact-table loads (`indiv`, `oppexp`, `oth`, `pas2`) when performance is the priority.
- Benchmark evidence (2026, serial dbt benchmark):
  - Warm-up measured pass (`serial-dbt-warmup`):
    - Extract approach: `4m 11.452s`
    - dbt `zipfs` approach: `2m 59.118s`
    - Improvement: `1m 12.334s` (~`28.8%` faster)
  - Fact-table subtotal:
    - Extract: `4m 06.617s`
    - dbt `zipfs`: `2m 49.526s`
    - Improvement: `1m 17.091s` (~`31.3%` faster)

- Operational note:
  - Run the benchmark dbt leg with serial threading (`--dbt-threads 1`) to avoid out-of-memory conditions observed under concurrent fact-table builds.
