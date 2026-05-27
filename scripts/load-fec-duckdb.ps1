<#
.SYNOPSIS
Loads FEC bulk ZIP files for a cycle into DuckDB raw tables.

.DESCRIPTION
This script reads ZIP artifacts from data/<cycle> and loads mapped ZIP entries
into DuckDB as cycle-scoped raw tables (raw_fec.<table>_<cycle>) using
zipfs archive paths.

.PARAMETER Cycle
Election cycle year (for example, 2026).

.PARAMETER Tables
Comma-separated or space-separated table names, for example:
  indiv,cm,cn
  indiv cm cn
Defaults to cm, cn, indiv, oppexp, oth, pas2, weball.

.PARAMETER DbPath
Path to the DuckDB database file.

.EXAMPLE
.\scripts\load-fec-duckdb.ps1 -Cycle 2026

.EXAMPLE
.\scripts\load-fec-duckdb.ps1 -Cycle 2026 -Tables indiv,cm,cn
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{4}$')]
    [string]$Cycle,
    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Tables,
    [string]$DbPath = 'db/fec.duckdb'
)

$ErrorActionPreference = 'Stop'

$defaultTables = @(
    'ccl',
    'cm',
    'cn',
    'indiv',
    'oppexp',
    'oth',
    'pas2',
    'weball'
)

if (-not $Tables -or $Tables.Count -eq 0) {
    $Tables = $defaultTables
}
else {
    $Tables = @(
        $Tables |
            ForEach-Object { $_ -split ',' } |
            ForEach-Object { $_.Trim().ToLowerInvariant() } |
            Where-Object { $_ -ne '' }
    )
}

$invalidTables = @($Tables | Where-Object { $_ -notin $defaultTables })
if ($invalidTables.Count -gt 0) {
    Write-Error "Unknown table name(s): $($invalidTables -join ', '). Valid tables: $($defaultTables -join ', ')."
    exit 1
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$cycleDir = Join-Path $repoRoot "data\$Cycle"
$yy = $Cycle.Substring(2)
$dbPathResolved = if ([System.IO.Path]::IsPathRooted($DbPath)) { $DbPath } else { Join-Path $repoRoot $DbPath }
$schemaSqlPath = Join-Path $repoRoot 'sql\schema\001_create_fec_schemas.sql'
$transformDir = Join-Path $repoRoot 'sql\transform'

# ZIP entry names per table — explicit to avoid ambiguity on multi-file archives.
$entryNameMap = @{
    'ccl'    = 'ccl.txt'
    'cm'     = 'cm.txt'
    'cn'     = 'cn.txt'
    'indiv'  = 'itcont.txt'  # non-standard: archive entry does not match table name
    'oppexp' = 'oppexp.txt'
    'oth'    = 'oth.txt'
    'pas2'   = 'pas2.txt'
    'weball' = 'weball.txt'
}

if (-not (Test-Path -Path $cycleDir -PathType Container)) {
    Write-Error "Cycle directory not found: $cycleDir"
    exit 1
}

if (-not (Test-Path -Path $transformDir -PathType Container)) {
    Write-Error "Transform SQL directory not found: $transformDir"
    exit 1
}

if (-not (Test-Path -Path $schemaSqlPath -PathType Leaf)) {
    Write-Error "Schema SQL not found: $schemaSqlPath"
    exit 1
}

New-Item -ItemType Directory -Path (Split-Path -Parent $dbPathResolved) -Force | Out-Null

# Initialize required schemas/tables.
$initCommand = ".read '$($schemaSqlPath.Replace('\', '/'))'"
duckdb $dbPathResolved -c $initCommand
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Failed to initialize DuckDB schema objects.'
    exit 1
}

# Ensure zipfs is available so DuckDB can read CSVs inside ZIP archives.
$zipFsInstallSql = 'INSTALL zipfs FROM community;'
duckdb $dbPathResolved -c $zipFsInstallSql
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Failed to install DuckDB zipfs extension from community.'
    exit 1
}

$loadedCount = 0
$skippedCount = 0
$failedCount = 0
$total = $Tables.Count
$index = 0

foreach ($table in $Tables) {
    $index++
    $zipName = "$table$yy.zip"
    $zipPath = Join-Path $cycleDir $zipName

    Write-Host "[$index/$total] Processing $zipName..."

    Write-Progress -Id 1 -Activity "Loading FEC tables for cycle $Cycle" -Status "[$index/$total] $zipName" -PercentComplete ([int](($index * 100) / $total))

    if (-not (Test-Path -Path $zipPath -PathType Leaf)) {
        Write-Warning "ZIP not found, skipping: $zipPath"
        $skippedCount++
        continue
    }

    try {
        $targetTable = "raw_fec.{0}_{1}" -f $table, $Cycle
        $loadStartedAtUtc = [DateTime]::UtcNow
        $zipPathSql = $zipPath.Replace("'", "''").Replace('\', '/')
        $zipPathNormalized = $zipPath.Replace('\', '/')
        $entryName = $entryNameMap[$table]
        $sourcePath = "zip://$zipPathNormalized/$entryName"
        $sourcePathSql = $sourcePath.Replace("'", "''")
        $entryNameHistorySql = "'$($entryName.Replace("'", "''"))'"
        Write-Verbose "Using DuckDB ZIP source path: $sourcePath"

        # Load the per-table SQL template and substitute runtime tokens.
        $sqlFilePath = Join-Path $transformDir "load_$table.sql"
        if (-not (Test-Path -Path $sqlFilePath -PathType Leaf)) {
            throw "Load SQL template not found: $sqlFilePath"
        }
        $loadSql = (Get-Content -Path $sqlFilePath -Raw) `
            -replace '\{TARGET_TABLE\}', $targetTable `
            -replace '\{SOURCE_PATH\}', $sourcePathSql `
            -replace '\{CYCLE\}', $Cycle `
            -replace '\{TABLE_NAME\}', $table `
            -replace '\{ZIP_PATH\}', $zipPathSql `
            -replace '\{ENTRY_NAME_SQL\}', $entryNameHistorySql

        duckdb $dbPathResolved -c $loadSql
        if ($LASTEXITCODE -ne 0) {
            throw "DuckDB load failed for $zipName"
        }

        $loadDurationMs = [int64](([DateTime]::UtcNow - $loadStartedAtUtc).TotalMilliseconds)
        $stateSql = @"
DELETE FROM etl.current_state
WHERE entity_type = 'table'
  AND cycle = $Cycle
  AND table_name = '$table';

INSERT INTO etl.current_state
SELECT
    COALESCE((SELECT MAX(state_id) + 1 FROM etl.current_state), 1) AS state_id,
    'table' AS entity_type,
    $Cycle AS cycle,
    '$table' AS table_name,
    '$zipName' AS entity_name,
    'load' AS last_operation,
    'Completed' AS operation_status,
    NULL AS source_url,
    '$zipPathSql' AS source_zip_path,
    $entryNameHistorySql AS source_entry_name,
    '$targetTable' AS target_table_name,
    NULL AS http_status,
    NULL AS content_length,
    (SELECT COUNT(*) FROM $targetTable) AS row_count,
    $loadDurationMs AS duration_ms,
    NULL AS response_date,
    NULL AS last_modified,
    NULL AS etag,
    NULL AS error_text,
    NOW() AS updated_at;
"@

        duckdb $dbPathResolved -c $stateSql
        if ($LASTEXITCODE -ne 0) {
            throw "Failed writing table current-state for $zipName"
        }

        $durationUpdateSql = @"
UPDATE etl.load_history
SET duration_ms = $loadDurationMs
WHERE load_id = (
    SELECT MAX(load_id)
    FROM etl.load_history
    WHERE cycle = $Cycle
      AND table_name = '$table'
      AND target_table_name = '$targetTable'
);
"@

        duckdb $dbPathResolved -c $durationUpdateSql
        if ($LASTEXITCODE -ne 0) {
            throw "Failed writing load duration for $zipName"
        }

        $loadedCount++
        Write-Host "[$index/$total] Loaded $zipName into $targetTable"
        Write-Verbose "LOADED  $zipName -> $targetTable"
    }
    catch {
        $failedCount++
        $loadDurationMs = if ($loadStartedAtUtc) { [int64](([DateTime]::UtcNow - $loadStartedAtUtc).TotalMilliseconds) } else { $null }
        $loadDurationSql = if ($null -eq $loadDurationMs) { 'NULL' } else { $loadDurationMs }
        $errorTextSql = $_.ToString().Replace("'", "''")
        $stateFailureSql = @"
DELETE FROM etl.current_state
WHERE entity_type = 'table'
  AND cycle = $Cycle
  AND table_name = '$table';

INSERT INTO etl.current_state
SELECT
    COALESCE((SELECT MAX(state_id) + 1 FROM etl.current_state), 1) AS state_id,
    'table' AS entity_type,
    $Cycle AS cycle,
    '$table' AS table_name,
    '$zipName' AS entity_name,
    'load' AS last_operation,
    'Failed' AS operation_status,
    NULL AS source_url,
    '$zipPathSql' AS source_zip_path,
    $entryNameHistorySql AS source_entry_name,
    '$targetTable' AS target_table_name,
    NULL AS http_status,
    NULL AS content_length,
    NULL AS row_count,
    $loadDurationSql AS duration_ms,
    NULL AS response_date,
    NULL AS last_modified,
    NULL AS etag,
    '$errorTextSql' AS error_text,
    NOW() AS updated_at;
"@

        duckdb $dbPathResolved -c $stateFailureSql | Out-Null
        Write-Error "Failed loading ${zipName}: $_"
        throw
    }
}

Write-Progress -Id 1 -Activity "Loading FEC tables for cycle $Cycle" -Completed
Write-Host "Load summary for ${Cycle}: loaded $loadedCount, skipped $skippedCount, failed $failedCount, total $total."

if ($failedCount -gt 0) {
    exit 1
}
