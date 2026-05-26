<#
.SYNOPSIS
Loads FEC bulk ZIP files for a cycle into DuckDB raw tables.

.DESCRIPTION
This script reads ZIP artifacts from data/<cycle>, extracts the first .txt/.csv
entry per ZIP to a temp location, and loads it into DuckDB as a cycle-scoped
raw table (raw_fec.<table>_<cycle>) using read_csv_auto.

.PARAMETER Cycle
Election cycle year (for example, 2026).

.PARAMETER Tables
Comma-separated or space-separated table names, for example:
  indiv,cm,cn
  indiv cm cn
Defaults to cm, cn, indiv, oppexp, oth, pas2, weball.

.PARAMETER DbPath
Path to the DuckDB database file.

.PARAMETER KeepExtracted
If set, keeps extracted temp source files under tmp/load/<cycle>.

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
    [string]$DbPath = 'db/fec.duckdb',
    [switch]$KeepExtracted
)

$ErrorActionPreference = 'Stop'

$defaultTables = @(
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
$tempRoot = Join-Path $repoRoot "tmp\load\$Cycle"
$schemaSqlPath = Join-Path $repoRoot 'sql\schema\001_create_fec_schemas.sql'

if (-not (Test-Path -Path $cycleDir -PathType Container)) {
    Write-Error "Cycle directory not found: $cycleDir"
    exit 1
}

if (-not (Test-Path -Path $schemaSqlPath -PathType Leaf)) {
    Write-Error "Schema SQL not found: $schemaSqlPath"
    exit 1
}

New-Item -ItemType Directory -Path (Split-Path -Parent $dbPathResolved) -Force | Out-Null
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

# Initialize required schemas/tables.
$initCommand = ".read '$($schemaSqlPath.Replace('\\', '/'))'"
duckdb $dbPathResolved -c $initCommand
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Failed to initialize DuckDB schema objects.'
    exit 1
}

$loadedCount = 0
$skippedCount = 0
$failedCount = 0
$total = $Tables.Count
$index = 0
$zipPathPattern = $null
$zipReadChecked = $false

Add-Type -AssemblyName System.IO.Compression.FileSystem

function Test-DuckDbCsvPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DbPath,
        [Parameter(Mandatory = $true)]
        [string]$CsvPath
    )

    $escapedCsvPath = $CsvPath.Replace("'", "''")
    $probeSql = @"
SELECT 1
FROM read_csv_auto(
    '$escapedCsvPath',
    delim='|',
    header=false,
    all_varchar=true,
    ignore_errors=true,
    sample_size=1000
)
LIMIT 1;
"@

    duckdb $DbPath -c $probeSql 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Build-ZipCsvPath {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('zip_slash', 'bang', 'double_colon')]
        [string]$Pattern,
        [Parameter(Mandatory = $true)]
        [string]$ZipPath,
        [Parameter(Mandatory = $true)]
        [string]$EntryPath
    )

    switch ($Pattern) {
        'zip_slash' { return "zip://$ZipPath/$EntryPath" }
        'bang' { return "$ZipPath!$EntryPath" }
        'double_colon' { return "$ZipPath::$EntryPath" }
    }
}

foreach ($table in $Tables) {
    $index++
    $zipName = "$table$yy.zip"
    $zipPath = Join-Path $cycleDir $zipName

    Write-Progress -Id 1 -Activity "Loading FEC tables for cycle $Cycle" -Status "[$index/$total] $zipName" -PercentComplete ([int](($index * 100) / $total))

    if (-not (Test-Path -Path $zipPath -PathType Leaf)) {
        Write-Warning "ZIP not found, skipping: $zipPath"
        $skippedCount++
        continue
    }

    $archive = $null
    $entry = $null
    $extractPath = $null

    try {
        $archive = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
        $entry = $archive.Entries |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_.Name) -and ($_.Name -match '\.(txt|csv)$') } |
            Select-Object -First 1

        if (-not $entry) {
            Write-Warning "No .txt/.csv entry found in ZIP, skipping: $zipPath"
            $skippedCount++
            continue
        }

        $targetTable = "raw_fec.{0}_{1}" -f $table, $Cycle
        $zipPathSql = $zipPath.Replace("'", "''").Replace('\\', '/')
        $entryNameSql = $entry.Name.Replace("'", "''")

        $zipPathNormalized = $zipPath.Replace('\\', '/')
        $entryPathNormalized = $entry.FullName.Replace('\\', '/')
        $sourcePath = $null

        if (-not $zipReadChecked) {
            foreach ($candidatePattern in @('zip_slash', 'bang', 'double_colon')) {
                $candidatePath = Build-ZipCsvPath -Pattern $candidatePattern -ZipPath $zipPathNormalized -EntryPath $entryPathNormalized
                if (Test-DuckDbCsvPath -DbPath $dbPathResolved -CsvPath $candidatePath) {
                    $zipPathPattern = $candidatePattern
                    Write-Verbose "Detected in-place ZIP read pattern: $zipPathPattern"
                    break
                }
            }

            if (-not $zipPathPattern) {
                Write-Verbose 'In-place ZIP reads not available. Falling back to extract-then-load.'
            }

            $zipReadChecked = $true
        }

        if ($zipPathPattern) {
            $sourcePath = Build-ZipCsvPath -Pattern $zipPathPattern -ZipPath $zipPathNormalized -EntryPath $entryPathNormalized
        }
        else {
            $extractFileName = "{0}_{1}_{2}" -f $table, $Cycle, $entry.Name
            $extractPath = Join-Path $tempRoot $extractFileName

            if (Test-Path $extractPath) {
                Remove-Item -Path $extractPath -Force
            }

            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $extractPath)
            $sourcePath = $extractPath.Replace('\\', '/')
        }

        $sourcePathSql = $sourcePath.Replace("'", "''")

        if ($table -eq 'cn') {
            $loadSql = @"
DROP TABLE IF EXISTS $targetTable;
CREATE TABLE $targetTable AS
SELECT
    CAND_ID,
    CAND_NAME,
    CAND_PTY_AFFILIATION,
    TRY_CAST(
        CASE
            WHEN LENGTH(TRIM(CAND_ELECTION_YR)) = 4 THEN TRIM(CAND_ELECTION_YR)
            ELSE NULL
        END AS SMALLINT
    ) AS CAND_ELECTION_YR,
    CAND_OFFICE_ST,
    CAND_OFFICE,
    CAND_OFFICE_DISTRICT,
    CAND_ICI,
    CAND_STATUS,
    CAND_PCC,
    CAND_ST1,
    CAND_ST2,
    CAND_CITY,
    CAND_ST,
    CAND_ZIP,
    '$zipPathSql' AS _source_zip_path,
    '$entryNameSql' AS _source_entry_name,
    NOW() AS _loaded_at
FROM read_csv(
    '$sourcePathSql',
    delim='|',
    header=false,
    all_varchar=true,
    null_padding=true,
    ignore_errors=true,
    sample_size=-1,
    columns={
        'CAND_ID':'VARCHAR',
        'CAND_NAME':'VARCHAR',
        'CAND_PTY_AFFILIATION':'VARCHAR',
        'CAND_ELECTION_YR':'VARCHAR',
        'CAND_OFFICE_ST':'VARCHAR',
        'CAND_OFFICE':'VARCHAR',
        'CAND_OFFICE_DISTRICT':'VARCHAR',
        'CAND_ICI':'VARCHAR',
        'CAND_STATUS':'VARCHAR',
        'CAND_PCC':'VARCHAR',
        'CAND_ST1':'VARCHAR',
        'CAND_ST2':'VARCHAR',
        'CAND_CITY':'VARCHAR',
        'CAND_ST':'VARCHAR',
        'CAND_ZIP':'VARCHAR'
    }
);

INSERT INTO etl.load_history
SELECT
    COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1) AS load_id,
    $Cycle,
    '$table',
    '$zipPathSql',
    '$entryNameSql',
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }
        else {
            $loadSql = @"
DROP TABLE IF EXISTS $targetTable;
CREATE TABLE $targetTable AS
SELECT
    *,
    '$zipPathSql' AS _source_zip_path,
    '$entryNameSql' AS _source_entry_name,
    NOW() AS _loaded_at
FROM read_csv_auto(
    '$sourcePathSql',
    delim='|',
    header=false,
    all_varchar=true,
    null_padding=true,
    ignore_errors=true,
    sample_size=-1
);

INSERT INTO etl.load_history
SELECT
    COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1) AS load_id,
    $Cycle,
    '$table',
    '$zipPathSql',
    '$entryNameSql',
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }

        duckdb $dbPathResolved -c $loadSql
        if ($LASTEXITCODE -ne 0) {
            throw "DuckDB load failed for $zipName"
        }

        $loadedCount++
        Write-Verbose "LOADED  $zipName -> $targetTable"
    }
    catch {
        $failedCount++
        Write-Error "Failed loading ${zipName}: $_"
    }
    finally {
        if ($archive) {
            $archive.Dispose()
        }

        if ((-not $KeepExtracted) -and $extractPath -and (Test-Path $extractPath)) {
            Remove-Item -Path $extractPath -Force
        }
    }
}

Write-Progress -Id 1 -Activity "Loading FEC tables for cycle $Cycle" -Completed
Write-Host "Load summary for ${Cycle}: loaded $loadedCount, skipped $skippedCount, failed $failedCount, total $total."

if ($failedCount -gt 0) {
    exit 1
}
