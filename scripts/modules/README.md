# ETLModule

This module provides reusable PowerShell ETL helpers with the **medallion architecture** pattern.
Default cycle-first landing layout: `data/{cycle}/bronze` (bronze zone).

## Exported commands

- `Sync-EtlArchiveSet`: Generic archive sync function for ETL landing zones.
- `Invoke-FecCycleRawSync`: FEC cycle wrapper that builds archive names and calls the generic sync function.
- `Expand-EtlCycleArchives`: Extracts zip archives from a cycle source layer to a target layer.
- `Invoke-EtlCycleLoad`: Runs ordered SQL batches in `sql/schema` then `sql/transform` via DuckDB.

## Usage

```powershell
Import-Module .\scripts\modules\ETLModule.psd1 -Force
Invoke-FecCycleRawSync -Cycle 2024
Expand-EtlCycleArchives -Cycle 2024
Invoke-EtlCycleLoad -Cycle 2024 -DuckDbPath db/fec.duckdb

# Optional medallion zone parameters
Invoke-FecCycleRawSync -Cycle 2024 -LandingZone bronze
Expand-EtlCycleArchives -Cycle 2024 -SourceZone bronze -TargetZone silver

# Incremental mode expands all paths, including indiv/by_date
Expand-EtlCycleArchives -Cycle 2024 -Incremental
```

## Script wrappers

- `scripts/Update-RawFile.ps1`: retrieve/update bronze archives for one cycle.
- `scripts/transform/extract_zips.ps1`: transform wrapper for archive extraction from bronze to silver.
- `scripts/load/invoke_load_cycle.ps1`: load wrapper for DuckDB SQL batches to create gold tables.
- `scripts/run_etl_cycle.ps1`: one command to run retrieve/transform/load for a cycle.

Default zone parameters use medallion naming: `bronze` (download) -> `silver` (extract) -> `gold` (load).

Extraction note: by default (non-incremental mode), `Expand-EtlCycleArchives` skips `indiv` `by_date` entries to speed up baseline and test runs. Use `-Incremental` to include `by_date`.

## `.psm1` vs `.psd1`

- `.psm1` is the module implementation file. It contains function code.
- `.psd1` is the module manifest file. It contains metadata such as version,
  exports, and module entrypoint (`RootModule`).