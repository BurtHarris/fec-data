# ETLModule

This module provides reusable PowerShell ETL helpers with a cycle-first
landing layout: `data/{cycle}/raw`.

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
```

## Script wrappers

- `scripts/Update-RawFile.ps1`: retrieve/update raw archives for one cycle.
- `scripts/transform/extract_zips.ps1`: transform wrapper for archive extraction.
- `scripts/load/invoke_load_cycle.ps1`: load wrapper for DuckDB SQL batches.
- `scripts/run_etl_cycle.ps1`: one command to run retrieve/transform/load for a cycle.

## `.psm1` vs `.psd1`

- `.psm1` is the module implementation file. It contains function code.
- `.psd1` is the module manifest file. It contains metadata such as version,
  exports, and module entrypoint (`RootModule`).