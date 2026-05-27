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
    [string]$DbPath = 'db/fec.duckdb',
    [string]$TimingLabel,
    [switch]$ShowProgress
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
$logsDir = Join-Path $repoRoot 'logs'
$timingRunsDir = Join-Path $logsDir 'load-timing'
$runStartedAtUtc = [DateTime]::UtcNow
$runTimestampToken = $runStartedAtUtc.ToString('yyyyMMdd_HHmmss')
$timingLabelSanitized = if ($TimingLabel) { ($TimingLabel -replace '[^A-Za-z0-9._-]', '_').Trim('_') } else { '' }
$timingLabelToken = if ([string]::IsNullOrWhiteSpace($timingLabelSanitized)) { 'default' } else { $timingLabelSanitized }
$timingRows = New-Object System.Collections.Generic.List[object]
$gitCommit = 'unknown'
$gitTreeState = 'unknown'

# ZIP entry names per table — explicit to avoid ambiguity on multi-file archives.
$entryNameMap = @{
    'ccl'    = 'ccl.txt'
    'cm'     = 'cm.txt'
    'cn'     = 'cn.txt'
    'indiv'  = 'itcont.txt'  # non-standard: archive entry does not match table name
    'oppexp' = 'oppexp.txt'
    'oth'    = 'itoth.txt'  # non-standard: archive entry does not match table name
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

Push-Location $repoRoot
try {
    $gitCommitText = (& git --no-pager rev-parse --short HEAD | Select-Object -Last 1)
    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($gitCommitText)) {
        $gitCommit = $gitCommitText.Trim()
    }
    else {
        Write-Warning 'Unable to resolve git commit SHA for timing metadata.'
    }

    $gitStatusText = (& git --no-pager status --porcelain)
    if ($LASTEXITCODE -eq 0) {
        $gitTreeState = if ([string]::IsNullOrWhiteSpace(($gitStatusText -join ''))) { 'clean' } else { 'dirty' }
    }
    else {
        Write-Warning 'Unable to resolve git working tree state for timing metadata.'
    }
}
finally {
    Pop-Location
}

New-Item -ItemType Directory -Path (Split-Path -Parent $dbPathResolved) -Force | Out-Null

function Invoke-DuckDbSql {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DbPath,
        [Parameter(Mandatory = $true)]
        [string]$Sql,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    Write-Host "[DUCKDB] $Description"
    duckdb $DbPath -c $Sql
}

function Invoke-DuckDbCsv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DbPath,
        [Parameter(Mandatory = $true)]
        [string]$Sql,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    Write-Host "[DUCKDB] $Description"
    return (duckdb -csv $DbPath $Sql)
}

# Initialize required schemas/tables.
$initCommand = ".read '$($schemaSqlPath.Replace('\', '/'))'"
Invoke-DuckDbSql -DbPath $dbPathResolved -Sql $initCommand -Description "Initializing schema objects from $schemaSqlPath"
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Failed to initialize DuckDB schema objects.'
    exit 1
}

# Ensure zipfs is available so DuckDB can read CSVs inside ZIP archives.
$zipFsInstallSql = 'INSTALL zipfs FROM community;'
Invoke-DuckDbSql -DbPath $dbPathResolved -Sql $zipFsInstallSql -Description 'Installing zipfs extension'
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Failed to install DuckDB zipfs extension from community.'
    exit 1
}

function Get-QaTableProfile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Table
    )

    switch ($Table) {
        'ccl' {
            return [PSCustomObject]@{
                CriticalNullColumns = @('CAND_ID', 'CAND_ELECTION_YR', 'FEC_ELECTION_YR', 'CMTE_ID', 'CMTE_TP', 'CMTE_DSGN', 'LINKAGE_ID')
                DuplicateKeyExpr = "CONCAT_WS('|', COALESCE(CAST(CAND_ID AS VARCHAR), ''), COALESCE(CAST(CAND_ELECTION_YR AS VARCHAR), ''), COALESCE(CAST(FEC_ELECTION_YR AS VARCHAR), ''), COALESCE(CMTE_ID, ''), COALESCE(CAST(LINKAGE_ID AS VARCHAR), ''))"
                DuplicateKeyLabel = 'CAND_ID|CAND_ELECTION_YR|FEC_ELECTION_YR|CMTE_ID|LINKAGE_ID'
            }
        }
        'cm' {
            return [PSCustomObject]@{
                CriticalNullColumns = @('CMTE_ID', 'CMTE_NM', 'CMTE_TP')
                DuplicateKeyExpr = "COALESCE(CMTE_ID, '')"
                DuplicateKeyLabel = 'CMTE_ID'
            }
        }
        'cn' {
            return [PSCustomObject]@{
                CriticalNullColumns = @('CAND_ID', 'CAND_NAME', 'CAND_PTY_AFFILIATION', 'CAND_ELECTION_YR')
                DuplicateKeyExpr = "COALESCE(CAND_ID, '')"
                DuplicateKeyLabel = 'CAND_ID'
            }
        }
        'indiv' {
            return [PSCustomObject]@{
                CriticalNullColumns = @('CMTE_ID', 'AMNDT_IND', 'RPT_TP', 'ENTITY_TP', 'NAME', 'TRANSACTION_DT', 'TRANSACTION_AMT', 'SUB_ID')
                DuplicateKeyExpr = "COALESCE(CAST(SUB_ID AS VARCHAR), '')"
                DuplicateKeyLabel = 'SUB_ID'
            }
        }
        'oth' {
            return [PSCustomObject]@{
                CriticalNullColumns = @('CMTE_ID', 'AMNDT_IND', 'RPT_TP', 'ENTITY_TP', 'NAME', 'TRANSACTION_DT', 'TRANSACTION_AMT', 'SUB_ID')
                DuplicateKeyExpr = "COALESCE(CAST(SUB_ID AS VARCHAR), '')"
                DuplicateKeyLabel = 'SUB_ID'
            }
        }
        'pas2' {
            return [PSCustomObject]@{
                CriticalNullColumns = @('CMTE_ID', 'AMNDT_IND', 'RPT_TP', 'ENTITY_TP', 'NAME', 'TRANSACTION_DT', 'TRANSACTION_AMT', 'SUB_ID', 'CAND_ID')
                DuplicateKeyExpr = "COALESCE(CAST(SUB_ID AS VARCHAR), '')"
                DuplicateKeyLabel = 'SUB_ID'
            }
        }
        'oppexp' {
            return [PSCustomObject]@{
                CriticalNullColumns = @('CMTE_ID', 'AMNDT_IND', 'RPT_YR', 'RPT_TP', 'NAME', 'TRANSACTION_DT', 'TRANSACTION_AMT', 'SUB_ID')
                DuplicateKeyExpr = "COALESCE(CAST(SUB_ID AS VARCHAR), '')"
                DuplicateKeyLabel = 'SUB_ID'
            }
        }
        'weball' {
            return [PSCustomObject]@{
                CriticalNullColumns = @('CAND_ID', 'CAND_NAME', 'PTY_CD', 'CAND_PTY_AFFILIATION', 'CVG_END_DT')
                DuplicateKeyExpr = "COALESCE(CAND_ID, '')"
                DuplicateKeyLabel = 'CAND_ID'
            }
        }
        default {
            throw "No QA profile configured for table '$Table'."
        }
    }
}

function Get-NextQaRunId {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DbPath
    )

    $runIdText = (
        Invoke-DuckDbCsv -DbPath $DbPath -Sql "SELECT COALESCE(MAX(run_id) + 1, 1) FROM etl.qa_run_summary;" -Description 'Selecting next QA run id' |
            Select-Object -Last 1
    ).Trim()
    if (-not $runIdText) {
        return [int64]1
    }

    return [int64]$runIdText
}

function Invoke-QaSqlTemplate {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DbPath,
        [Parameter(Mandatory = $true)]
        [string]$TemplatePath,
        [Parameter(Mandatory = $true)]
        [hashtable]$Replacements
    )

    $sql = Get-Content -Path $TemplatePath -Raw
    foreach ($pair in $Replacements.GetEnumerator()) {
        $sql = $sql.Replace($pair.Key, $pair.Value)
    }

    Invoke-DuckDbSql -DbPath $DbPath -Sql $sql -Description "Executing QA SQL template $(Split-Path -Leaf $TemplatePath)"
    if ($LASTEXITCODE -ne 0) {
        throw "QA SQL execution failed for template '$TemplatePath'."
    }
}

function Invoke-QaAuditsForTable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DbPath,
        [Parameter(Mandatory = $true)]
        [int]$Cycle,
        [Parameter(Mandatory = $true)]
        [string]$Table,
        [Parameter(Mandatory = $true)]
        [string]$TargetTable
    )

    $profile = Get-QaTableProfile -Table $Table
    $runId = Get-NextQaRunId -DbPath $DbPath
    $qaDir = Join-Path $repoRoot 'sql\qa'
    $nullMetricsCte = @()

    foreach ($column in $profile.CriticalNullColumns) {
        $nullMetricsCte += @"
SELECT
    $runId AS run_id,
    $Cycle AS cycle,
    '$Table' AS table_name,
    'null_rate' AS metric_name,
    '$column' AS issue_key,
    CAST(COUNT(*) AS DOUBLE) AS metric_value,
    COUNT(*) AS issue_count,
    CASE WHEN COUNT(*) > 0 THEN 'warn' ELSE 'pass' END AS status,
    'null_count=' || CAST(COUNT(*) AS VARCHAR) || '; total=' || CAST((SELECT COUNT(*) FROM $TargetTable) AS VARCHAR) AS issue_details,
    NOW() AS computed_at
FROM $TargetTable
WHERE $column IS NULL
"@
    }

    Invoke-QaSqlTemplate `
        -DbPath $DbPath `
        -TemplatePath (Join-Path $qaDir '01_null_rate_audit.sql') `
        -Replacements @{
            '{{RUN_ID}}' = $runId.ToString()
            '{{CYCLE}}' = $Cycle.ToString()
            '{{TABLE_NAME}}' = "'$Table'"
            '{{TARGET_TABLE}}' = $TargetTable
            '{{NULL_METRICS_QUERY}}' = ($nullMetricsCte -join "`nUNION ALL`n")
        }

    Invoke-QaSqlTemplate `
        -DbPath $DbPath `
        -TemplatePath (Join-Path $qaDir '02_duplicate_key_audit.sql') `
        -Replacements @{
            '{{RUN_ID}}' = $runId.ToString()
            '{{CYCLE}}' = $Cycle.ToString()
            '{{TABLE_NAME}}' = "'$Table'"
            '{{TARGET_TABLE}}' = $TargetTable
            '{{KEY_EXPR}}' = $profile.DuplicateKeyExpr
            '{{KEY_LABEL}}' = "'$($profile.DuplicateKeyLabel)'"
        }

    $qualityStatusSql = @"
UPDATE etl.current_state
SET quality_status = (
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM etl.qa_issue_log
            WHERE run_id = $runId
              AND cycle = $Cycle
              AND table_name = '$Table'
              AND issue_count > 0
        ) THEN 'warn'
        ELSE 'pass'
    END
)
WHERE entity_type = 'table'
  AND cycle = $Cycle
  AND table_name = '$Table';
"@

    Invoke-DuckDbSql -DbPath $DbPath -Sql $qualityStatusSql -Description "Updating QA quality status for table $Table"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed updating QA quality status for table '$Table'."
    }
}

function Test-DuckDbRawTableExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DbPath,
        [Parameter(Mandatory = $true)]
        [string]$RawTableName
    )

        $tableNameOnly = $RawTableName
        if ($tableNameOnly -like 'raw_fec.*') {
                $tableNameOnly = $tableNameOnly.Substring(8)
        }

        $existsText = (
        Invoke-DuckDbCsv -DbPath $DbPath -Description "Checking existence of raw_fec.$tableNameOnly" -Sql @"
SELECT COUNT(*)
FROM information_schema.tables
WHERE table_schema = 'raw_fec'
    AND table_name = '$tableNameOnly';
"@ |
            Select-Object -Last 1
    ).Trim()

    return ([int64]$existsText -gt 0)
}

function Get-QaCrossTableProfile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Table
    )

    $currentYear = [int]$Cycle

    switch ($Table) {
        'ccl' {
            return [PSCustomObject]@{
                ReferentialChecks = @(
                    [PSCustomObject]@{ IssueKey = 'CAND_ID->cn'; IssueDetails = 'candidate missing from cn'; JoinColumn = 'CAND_ID'; RefTable = "raw_fec.cn_$Cycle"; RefColumn = 'CAND_ID' },
                    [PSCustomObject]@{ IssueKey = 'CMTE_ID->cm'; IssueDetails = 'committee missing from cm'; JoinColumn = 'CMTE_ID'; RefTable = "raw_fec.cm_$Cycle"; RefColumn = 'CMTE_ID' }
                )
                DomainChecks = @(
                    [PSCustomObject]@{ IssueKey = 'CAND_ELECTION_YR_range'; IssueDetails = 'candidate election year out of range'; Condition = "CAND_ELECTION_YR IS NOT NULL AND (CAND_ELECTION_YR < 1900 OR CAND_ELECTION_YR > 2100)" }
                )
            }
        }
        'indiv' {
            return [PSCustomObject]@{
                ReferentialChecks = @(
                    [PSCustomObject]@{ IssueKey = 'CMTE_ID->cm'; IssueDetails = 'committee missing from cm'; JoinColumn = 'CMTE_ID'; RefTable = "raw_fec.cm_$Cycle"; RefColumn = 'CMTE_ID' }
                )
                DomainChecks = @(
                    [PSCustomObject]@{ IssueKey = 'TRANSACTION_DT_future'; IssueDetails = 'transaction date is in the future'; Condition = "TRANSACTION_DT IS NOT NULL AND TRANSACTION_DT > CURRENT_DATE" },
                    [PSCustomObject]@{ IssueKey = 'TRANSACTION_AMT_negative'; IssueDetails = 'transaction amount is negative'; Condition = "TRANSACTION_AMT IS NOT NULL AND TRANSACTION_AMT < 0" }
                )
            }
        }
        'oth' {
            return [PSCustomObject]@{
                ReferentialChecks = @(
                    [PSCustomObject]@{ IssueKey = 'CMTE_ID->cm'; IssueDetails = 'committee missing from cm'; JoinColumn = 'CMTE_ID'; RefTable = "raw_fec.cm_$Cycle"; RefColumn = 'CMTE_ID' }
                )
                DomainChecks = @(
                    [PSCustomObject]@{ IssueKey = 'TRANSACTION_DT_future'; IssueDetails = 'transaction date is in the future'; Condition = "TRANSACTION_DT IS NOT NULL AND TRANSACTION_DT > CURRENT_DATE" },
                    [PSCustomObject]@{ IssueKey = 'TRANSACTION_AMT_negative'; IssueDetails = 'transaction amount is negative'; Condition = "TRANSACTION_AMT IS NOT NULL AND TRANSACTION_AMT < 0" }
                )
            }
        }
        'pas2' {
            return [PSCustomObject]@{
                ReferentialChecks = @(
                    [PSCustomObject]@{ IssueKey = 'CMTE_ID->cm'; IssueDetails = 'committee missing from cm'; JoinColumn = 'CMTE_ID'; RefTable = "raw_fec.cm_$Cycle"; RefColumn = 'CMTE_ID' },
                    [PSCustomObject]@{ IssueKey = 'CAND_ID->cn'; IssueDetails = 'candidate missing from cn'; JoinColumn = 'CAND_ID'; RefTable = "raw_fec.cn_$Cycle"; RefColumn = 'CAND_ID' }
                )
                DomainChecks = @(
                    [PSCustomObject]@{ IssueKey = 'TRANSACTION_DT_future'; IssueDetails = 'transaction date is in the future'; Condition = "TRANSACTION_DT IS NOT NULL AND TRANSACTION_DT > CURRENT_DATE" },
                    [PSCustomObject]@{ IssueKey = 'TRANSACTION_AMT_negative'; IssueDetails = 'transaction amount is negative'; Condition = "TRANSACTION_AMT IS NOT NULL AND TRANSACTION_AMT < 0" }
                )
            }
        }
        'oppexp' {
            return [PSCustomObject]@{
                ReferentialChecks = @(
                    [PSCustomObject]@{ IssueKey = 'CMTE_ID->cm'; IssueDetails = 'committee missing from cm'; JoinColumn = 'CMTE_ID'; RefTable = "raw_fec.cm_$Cycle"; RefColumn = 'CMTE_ID' }
                )
                DomainChecks = @(
                    [PSCustomObject]@{ IssueKey = 'RPT_YR_range'; IssueDetails = 'report year out of range'; Condition = "RPT_YR IS NOT NULL AND (RPT_YR < 1900 OR RPT_YR > $currentYear + 1)" },
                    [PSCustomObject]@{ IssueKey = 'TRANSACTION_DT_future'; IssueDetails = 'transaction date is in the future'; Condition = "TRANSACTION_DT IS NOT NULL AND TRANSACTION_DT > CURRENT_DATE" },
                    [PSCustomObject]@{ IssueKey = 'TRANSACTION_AMT_negative'; IssueDetails = 'transaction amount is negative'; Condition = "TRANSACTION_AMT IS NOT NULL AND TRANSACTION_AMT < 0" }
                )
            }
        }
        'weball' {
            return [PSCustomObject]@{
                ReferentialChecks = @(
                    [PSCustomObject]@{ IssueKey = 'CAND_ID->cn'; IssueDetails = 'candidate missing from cn'; JoinColumn = 'CAND_ID'; RefTable = "raw_fec.cn_$Cycle"; RefColumn = 'CAND_ID' }
                )
                DomainChecks = @(
                    [PSCustomObject]@{ IssueKey = 'CVG_END_DT_future'; IssueDetails = 'coverage end date is in the future'; Condition = "CVG_END_DT IS NOT NULL AND CVG_END_DT > CURRENT_DATE" },
                    [PSCustomObject]@{ IssueKey = 'GEN_ELECTION_PRECENT_range'; IssueDetails = 'general election percent is out of range'; Condition = "GEN_ELECTION_PRECENT IS NOT NULL AND (GEN_ELECTION_PRECENT < 0 OR GEN_ELECTION_PRECENT > 1)" }
                )
            }
        }
        default {
            return [PSCustomObject]@{
                ReferentialChecks = @()
                DomainChecks = @()
            }
        }
    }
}

function Get-QaMetricQueries {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Table,
        [Parameter(Mandatory = $true)]
        [string]$TargetTable,
        [Parameter(Mandatory = $true)]
        [int]$RunId,
        [Parameter(Mandatory = $true)]
        [string]$MetricName,
        [Parameter(Mandatory = $true)]
        [string]$IssueType,
        [Parameter(Mandatory = $true)]
        [System.Collections.IEnumerable]$Checks
    )

    $queries = @()
    foreach ($check in $Checks) {
        if (-not (Test-DuckDbRawTableExists -DbPath $dbPathResolved -RawTableName $check.RefTable.Split('.')[1])) {
            continue
        }

        $queries += @"
SELECT
    $RunId AS run_id,
    $Cycle AS cycle,
    '$Table' AS table_name,
    '$MetricName' AS metric_name,
    '$($check.IssueKey)' AS issue_key,
    CAST(COUNT(*) AS DOUBLE) AS metric_value,
    COUNT(*) AS issue_count,
    CASE WHEN COUNT(*) > 0 THEN 'warn' ELSE 'pass' END AS status,
    '$($check.IssueDetails)' || '; ref_table=' || '$($check.RefTable)' AS issue_details,
    NOW() AS computed_at
FROM $TargetTable t
LEFT JOIN $($check.RefTable) r
    ON t.$($check.JoinColumn) = r.$($check.RefColumn)
WHERE t.$($check.JoinColumn) IS NOT NULL
  AND r.$($check.RefColumn) IS NULL
"@
    }

    return ($queries -join "`nUNION ALL`n")
}

function Invoke-QaCrossTableAuditsForTable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DbPath,
        [Parameter(Mandatory = $true)]
        [int]$Cycle,
        [Parameter(Mandatory = $true)]
        [string]$Table,
        [Parameter(Mandatory = $true)]
        [string]$TargetTable
    )

    $profile = Get-QaCrossTableProfile -Table $Table
    $runId = Get-NextQaRunId -DbPath $DbPath
    $qaDir = Join-Path $repoRoot 'sql\qa'

    $referentialQueries = Get-QaMetricQueries -Table $Table -TargetTable $TargetTable -RunId $runId -MetricName 'referential_orphan' -IssueType 'referential_orphan' -Checks $profile.ReferentialChecks
    if ($referentialQueries) {
        Invoke-QaSqlTemplate `
            -DbPath $DbPath `
            -TemplatePath (Join-Path $qaDir '03_referential_orphan_audit.sql') `
            -Replacements @{
                '{{RUN_ID}}' = $runId.ToString()
                '{{CYCLE}}' = $Cycle.ToString()
                '{{TABLE_NAME}}' = "'$Table'"
                '{{TARGET_TABLE}}' = $TargetTable
                '{{REFERENTIAL_METRICS_QUERY}}' = $referentialQueries
            }
    }

    $domainQueries = @()
    foreach ($check in $profile.DomainChecks) {
        $domainQueries += @"
SELECT
    $runId AS run_id,
    $Cycle AS cycle,
    '$Table' AS table_name,
    'domain_violation' AS metric_name,
    '$($check.IssueKey)' AS issue_key,
    CAST(COUNT(*) AS DOUBLE) AS metric_value,
    COUNT(*) AS issue_count,
    CASE WHEN COUNT(*) > 0 THEN 'warn' ELSE 'pass' END AS status,
    '$($check.IssueDetails)' AS issue_details,
    NOW() AS computed_at
FROM $TargetTable
WHERE $($check.Condition)
"@
    }

    if ($domainQueries) {
        Invoke-QaSqlTemplate `
            -DbPath $DbPath `
            -TemplatePath (Join-Path $qaDir '04_amount_date_domain_audit.sql') `
            -Replacements @{
                '{{RUN_ID}}' = $runId.ToString()
                '{{CYCLE}}' = $Cycle.ToString()
                '{{TABLE_NAME}}' = "'$Table'"
                '{{TARGET_TABLE}}' = $TargetTable
                '{{DOMAIN_METRICS_QUERY}}' = ($domainQueries -join "`nUNION ALL`n")
            }
    }

    if ($referentialQueries -or $domainQueries) {
        $qualityStatusSql = @"
UPDATE etl.current_state
SET quality_status = (
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM etl.qa_issue_log
            WHERE cycle = $Cycle
              AND table_name = '$Table'
              AND issue_count > 0
        ) THEN 'warn'
        ELSE 'pass'
    END
)
WHERE entity_type = 'table'
  AND cycle = $Cycle
  AND table_name = '$Table';
"@

        Invoke-DuckDbSql -DbPath $DbPath -Sql $qualityStatusSql -Description "Updating cross-table QA status for table $Table"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed updating cross-table QA quality status for table '$Table'."
        }
    }
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

    if ($ShowProgress) {
        Write-Progress -Id 1 -Activity "Loading FEC tables for cycle $Cycle" -Status "[$index/$total] $zipName" -PercentComplete ([int](($index * 100) / $total))
    }

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

        Invoke-DuckDbSql -DbPath $dbPathResolved -Sql $loadSql -Description "Loading $zipName into $targetTable"
        if ($LASTEXITCODE -ne 0) {
            throw "DuckDB load failed for $zipName"
        }

        $loadDurationMs = [int64](([DateTime]::UtcNow - $loadStartedAtUtc).TotalMilliseconds)
        $stateSql = @"
DELETE FROM etl.current_state
WHERE entity_type = 'table'
  AND cycle = $Cycle
  AND table_name = '$table';

INSERT INTO etl.current_state (
    state_id,
    entity_type,
    cycle,
    table_name,
    entity_name,
    last_operation,
    operation_status,
    quality_status,
    source_url,
    source_zip_path,
    source_entry_name,
    target_table_name,
    http_status,
    content_length,
    row_count,
    duration_ms,
    response_date,
    last_modified,
    etag,
    error_text,
    updated_at
)
SELECT
    COALESCE((SELECT MAX(state_id) + 1 FROM etl.current_state), 1) AS state_id,
    'table' AS entity_type,
    $Cycle AS cycle,
    '$table' AS table_name,
    '$zipName' AS entity_name,
    'load' AS last_operation,
    'Completed' AS operation_status,
    'pass' AS quality_status,
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

        Invoke-DuckDbSql -DbPath $dbPathResolved -Sql $stateSql -Description "Updating current_state for $zipName"
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

        Invoke-DuckDbSql -DbPath $dbPathResolved -Sql $durationUpdateSql -Description "Updating load duration for $zipName"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed writing load duration for $zipName"
        }

        Invoke-QaAuditsForTable -DbPath $dbPathResolved -Cycle $Cycle -Table $table -TargetTable $targetTable

        $loadedCount++
        $timingRows.Add([PSCustomObject]@{
                run_started_utc  = $runStartedAtUtc.ToString('o')
                cycle            = [int]$Cycle
                timing_label     = $timingLabelToken
                git_commit       = $gitCommit
                git_tree_state   = $gitTreeState
                table_name       = $table
                zip_name         = $zipName
                target_table     = $targetTable
                status           = 'loaded'
                duration_ms      = $loadDurationMs
                measured_at_utc  = [DateTime]::UtcNow.ToString('o')
                error_text       = $null
            }) | Out-Null
        Write-Host "[$index/$total] Loaded $zipName into $targetTable in $loadDurationMs ms"
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

INSERT INTO etl.current_state (
    state_id,
    entity_type,
    cycle,
    table_name,
    entity_name,
    last_operation,
    operation_status,
    quality_status,
    source_url,
    source_zip_path,
    source_entry_name,
    target_table_name,
    http_status,
    content_length,
    row_count,
    duration_ms,
    response_date,
    last_modified,
    etag,
    error_text,
    updated_at
)
SELECT
    COALESCE((SELECT MAX(state_id) + 1 FROM etl.current_state), 1) AS state_id,
    'table' AS entity_type,
    $Cycle AS cycle,
    '$table' AS table_name,
    '$zipName' AS entity_name,
    'load' AS last_operation,
    'Failed' AS operation_status,
    'error' AS quality_status,
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

$timingRows.Add([PSCustomObject]@{
        run_started_utc  = $runStartedAtUtc.ToString('o')
        cycle            = [int]$Cycle
        timing_label     = $timingLabelToken
        git_commit       = $gitCommit
        git_tree_state   = $gitTreeState
        table_name       = $table
        zip_name         = $zipName
        target_table     = if ($targetTable) { $targetTable } else { $null }
        status           = 'failed'
        duration_ms      = $loadDurationMs
        measured_at_utc  = [DateTime]::UtcNow.ToString('o')
        error_text       = $_.ToString()
    }) | Out-Null
Invoke-DuckDbSql -DbPath $dbPathResolved -Sql $stateFailureSql -Description "Recording failed current_state for $zipName"
Write-Error "Failed loading ${zipName}: $_"
throw
    }
}

foreach ($table in $Tables) {
    $targetTable = "raw_fec.{0}_{1}" -f $table, $Cycle
    if (Test-DuckDbRawTableExists -DbPath $dbPathResolved -RawTableName $targetTable) {
        Invoke-QaCrossTableAuditsForTable -DbPath $dbPathResolved -Cycle $Cycle -Table $table -TargetTable $targetTable
    }
}

if ($ShowProgress) {
    Write-Progress -Id 1 -Activity "Loading FEC tables for cycle $Cycle" -Completed
}
if ($timingRows.Count -gt 0) {
    New-Item -ItemType Directory -Path $timingRunsDir -Force | Out-Null
    $timingFileName = "load_timing_${Cycle}_${runTimestampToken}_${timingLabelToken}_${gitCommit}_${gitTreeState}.csv"
    $timingFilePath = Join-Path $timingRunsDir $timingFileName
    $timingRows | Export-Csv -Path $timingFilePath -NoTypeInformation -Encoding UTF8
    Write-Host "Timing report written: $timingFilePath"
}
Write-Host "Load summary for ${Cycle}: loaded $loadedCount, skipped $skippedCount, failed $failedCount, total $total."

if ($failedCount -gt 0) {
    exit 1
}
