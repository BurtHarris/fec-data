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

if (-not (Test-Path -Path $cycleDir -PathType Container)) {
    Write-Error "Cycle directory not found: $cycleDir"
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
        $zipPathSql = $zipPath.Replace("'", "''").Replace('\', '/')
        $zipPathNormalized = $zipPath.Replace('\', '/')
        if ($table -eq 'indiv') {
            $entryName = 'itcont.txt'
            $sourcePath = "zip://$zipPathNormalized/$entryName"
            Write-Verbose "Using explicit ZIP entry '$entryName' for indiv."
        }
        else {
            $entryName = $null
            $sourcePath = "zip://$zipPathNormalized"
            Write-Verbose "Using bare ZIP archive path for single-file table '$table'."
        }
        Write-Verbose "Using DuckDB ZIP source path: $sourcePath"

        $sourcePathSql = $sourcePath.Replace("'", "''")
        $entryNameSql = if ($entryName) { $entryName.Replace("'", "''") } else { $null }
        $entryNameHistorySql = if ([string]::IsNullOrWhiteSpace($entryNameSql)) { 'NULL' } else { "'$entryNameSql'" }

        # Provenance is tracked at load-operation level in etl.load_history.

        if ($table -eq 'ccl') {
            $loadSql = @"
LOAD zipfs;
DROP TABLE IF EXISTS $targetTable;
CREATE TABLE $targetTable AS
SELECT
    CAND_ID,
    TRY_CAST(
        CASE
            WHEN LENGTH(TRIM(CAND_ELECTION_YR)) = 4 THEN TRIM(CAND_ELECTION_YR)
            ELSE NULL
        END AS SMALLINT
    ) AS CAND_ELECTION_YR,
    TRY_CAST(
        CASE
            WHEN LENGTH(TRIM(FEC_ELECTION_YR)) = 4 THEN TRIM(FEC_ELECTION_YR)
            ELSE NULL
        END AS SMALLINT
    ) AS FEC_ELECTION_YR,
    CMTE_ID,
    CMTE_TP,
    CMTE_DSGN,
    TRY_CAST(NULLIF(TRIM(LINKAGE_ID), '') AS BIGINT) AS LINKAGE_ID
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
        'CAND_ELECTION_YR':'VARCHAR',
        'FEC_ELECTION_YR':'VARCHAR',
        'CMTE_ID':'VARCHAR',
        'CMTE_TP':'VARCHAR',
        'CMTE_DSGN':'VARCHAR',
        'LINKAGE_ID':'VARCHAR'
    }
);

INSERT INTO etl.load_history
SELECT
    COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1) AS load_id,
    $Cycle,
    '$table',
    '$zipPathSql',
    $entryNameHistorySql,
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }
        elseif ($table -eq 'cm') {
            $loadSql = @"
LOAD zipfs;
DROP TABLE IF EXISTS $targetTable;
CREATE TABLE $targetTable AS
SELECT
    CMTE_ID,
    CMTE_NM,
    TRES_NM,
    CMTE_ST1,
    CMTE_ST2,
    CMTE_CITY,
    CMTE_ST,
    CMTE_ZIP,
    CMTE_DSGN,
    CMTE_TP,
    CMTE_PTY_AFFILIATION,
    CMTE_FILING_FREQ,
    ORG_TP,
    CONNECTED_ORG_NM,
    CAND_ID
FROM read_csv(
    '$sourcePathSql',
    delim='|',
    header=false,
    all_varchar=true,
    null_padding=true,
    ignore_errors=true,
    sample_size=-1,
    columns={
        'CMTE_ID':'VARCHAR',
        'CMTE_NM':'VARCHAR',
        'TRES_NM':'VARCHAR',
        'CMTE_ST1':'VARCHAR',
        'CMTE_ST2':'VARCHAR',
        'CMTE_CITY':'VARCHAR',
        'CMTE_ST':'VARCHAR',
        'CMTE_ZIP':'VARCHAR',
        'CMTE_DSGN':'VARCHAR',
        'CMTE_TP':'VARCHAR',
        'CMTE_PTY_AFFILIATION':'VARCHAR',
        'CMTE_FILING_FREQ':'VARCHAR',
        'ORG_TP':'VARCHAR',
        'CONNECTED_ORG_NM':'VARCHAR',
        'CAND_ID':'VARCHAR'
    }
);

INSERT INTO etl.load_history
SELECT
    COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1) AS load_id,
    $Cycle,
    '$table',
    '$zipPathSql',
    $entryNameHistorySql,
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }
        elseif ($table -eq 'cn') {
            $loadSql = @"
LOAD zipfs;
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
    CAND_ZIP
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
    $entryNameHistorySql,
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }
        elseif ($table -eq 'indiv') {
            $loadSql = @"
LOAD zipfs;
DROP TABLE IF EXISTS $targetTable;
CREATE TABLE $targetTable AS
SELECT
    CMTE_ID,
    AMNDT_IND,
    RPT_TP,
    TRANSACTION_PGI,
    IMAGE_NUM,
    TRANSACTION_TP,
    ENTITY_TP,
    NAME,
    CITY,
    STATE,
    ZIP_CODE,
    EMPLOYER,
    OCCUPATION,
    CAST(TRY_STRPTIME(NULLIF(TRIM(TRANSACTION_DT), ''), '%m%d%Y') AS DATE) AS TRANSACTION_DT,
    TRY_CAST(NULLIF(TRIM(TRANSACTION_AMT), '') AS DECIMAL(14,2)) AS TRANSACTION_AMT,
    OTHER_ID,
    TRAN_ID,
    TRY_CAST(NULLIF(TRIM(FILE_NUM), '') AS BIGINT) AS FILE_NUM,
    MEMO_CD,
    MEMO_TEXT,
    TRY_CAST(NULLIF(TRIM(SUB_ID), '') AS BIGINT) AS SUB_ID
FROM read_csv(
    '$sourcePathSql',
    delim='|',
    header=false,
    all_varchar=true,
    null_padding=true,
    ignore_errors=true,
    sample_size=-1,
    columns={
        'CMTE_ID':'VARCHAR',
        'AMNDT_IND':'VARCHAR',
        'RPT_TP':'VARCHAR',
        'TRANSACTION_PGI':'VARCHAR',
        'IMAGE_NUM':'VARCHAR',
        'TRANSACTION_TP':'VARCHAR',
        'ENTITY_TP':'VARCHAR',
        'NAME':'VARCHAR',
        'CITY':'VARCHAR',
        'STATE':'VARCHAR',
        'ZIP_CODE':'VARCHAR',
        'EMPLOYER':'VARCHAR',
        'OCCUPATION':'VARCHAR',
        'TRANSACTION_DT':'VARCHAR',
        'TRANSACTION_AMT':'VARCHAR',
        'OTHER_ID':'VARCHAR',
        'TRAN_ID':'VARCHAR',
        'FILE_NUM':'VARCHAR',
        'MEMO_CD':'VARCHAR',
        'MEMO_TEXT':'VARCHAR',
        'SUB_ID':'VARCHAR'
    }
);

INSERT INTO etl.load_history
SELECT
    COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1) AS load_id,
    $Cycle,
    '$table',
    '$zipPathSql',
    $entryNameHistorySql,
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }
        elseif ($table -eq 'oth') {
            $loadSql = @"
LOAD zipfs;
DROP TABLE IF EXISTS $targetTable;
CREATE TABLE $targetTable AS
SELECT
    CMTE_ID,
    AMNDT_IND,
    RPT_TP,
    TRANSACTION_PGI,
    IMAGE_NUM,
    TRANSACTION_TP,
    ENTITY_TP,
    NAME,
    CITY,
    STATE,
    ZIP_CODE,
    EMPLOYER,
    OCCUPATION,
    CAST(TRY_STRPTIME(NULLIF(TRIM(TRANSACTION_DT), ''), '%m%d%Y') AS DATE) AS TRANSACTION_DT,
    TRY_CAST(NULLIF(TRIM(TRANSACTION_AMT), '') AS DECIMAL(14,2)) AS TRANSACTION_AMT,
    OTHER_ID,
    TRAN_ID,
    TRY_CAST(NULLIF(TRIM(FILE_NUM), '') AS BIGINT) AS FILE_NUM,
    MEMO_CD,
    MEMO_TEXT,
    TRY_CAST(NULLIF(TRIM(SUB_ID), '') AS BIGINT) AS SUB_ID
FROM read_csv(
    '$sourcePathSql',
    delim='|',
    header=false,
    all_varchar=true,
    null_padding=true,
    ignore_errors=true,
    sample_size=-1,
    columns={
        'CMTE_ID':'VARCHAR',
        'AMNDT_IND':'VARCHAR',
        'RPT_TP':'VARCHAR',
        'TRANSACTION_PGI':'VARCHAR',
        'IMAGE_NUM':'VARCHAR',
        'TRANSACTION_TP':'VARCHAR',
        'ENTITY_TP':'VARCHAR',
        'NAME':'VARCHAR',
        'CITY':'VARCHAR',
        'STATE':'VARCHAR',
        'ZIP_CODE':'VARCHAR',
        'EMPLOYER':'VARCHAR',
        'OCCUPATION':'VARCHAR',
        'TRANSACTION_DT':'VARCHAR',
        'TRANSACTION_AMT':'VARCHAR',
        'OTHER_ID':'VARCHAR',
        'TRAN_ID':'VARCHAR',
        'FILE_NUM':'VARCHAR',
        'MEMO_CD':'VARCHAR',
        'MEMO_TEXT':'VARCHAR',
        'SUB_ID':'VARCHAR'
    }
);

INSERT INTO etl.load_history
SELECT
    COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1) AS load_id,
    $Cycle,
    '$table',
    '$zipPathSql',
    $entryNameHistorySql,
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }
        elseif ($table -eq 'pas2') {
            $loadSql = @"
LOAD zipfs;
DROP TABLE IF EXISTS $targetTable;
CREATE TABLE $targetTable AS
SELECT
    CMTE_ID,
    AMNDT_IND,
    RPT_TP,
    TRANSACTION_PGI,
    IMAGE_NUM,
    TRANSACTION_TP,
    ENTITY_TP,
    NAME,
    CITY,
    STATE,
    ZIP_CODE,
    EMPLOYER,
    OCCUPATION,
    CAST(TRY_STRPTIME(NULLIF(TRIM(TRANSACTION_DT), ''), '%m%d%Y') AS DATE) AS TRANSACTION_DT,
    TRY_CAST(NULLIF(TRIM(TRANSACTION_AMT), '') AS DECIMAL(14,2)) AS TRANSACTION_AMT,
    OTHER_ID,
    CAND_ID,
    TRAN_ID,
    TRY_CAST(NULLIF(TRIM(FILE_NUM), '') AS BIGINT) AS FILE_NUM,
    MEMO_CD,
    MEMO_TEXT,
    TRY_CAST(NULLIF(TRIM(SUB_ID), '') AS BIGINT) AS SUB_ID
FROM read_csv(
    '$sourcePathSql',
    delim='|',
    header=false,
    all_varchar=true,
    null_padding=true,
    ignore_errors=true,
    sample_size=-1,
    columns={
        'CMTE_ID':'VARCHAR',
        'AMNDT_IND':'VARCHAR',
        'RPT_TP':'VARCHAR',
        'TRANSACTION_PGI':'VARCHAR',
        'IMAGE_NUM':'VARCHAR',
        'TRANSACTION_TP':'VARCHAR',
        'ENTITY_TP':'VARCHAR',
        'NAME':'VARCHAR',
        'CITY':'VARCHAR',
        'STATE':'VARCHAR',
        'ZIP_CODE':'VARCHAR',
        'EMPLOYER':'VARCHAR',
        'OCCUPATION':'VARCHAR',
        'TRANSACTION_DT':'VARCHAR',
        'TRANSACTION_AMT':'VARCHAR',
        'OTHER_ID':'VARCHAR',
        'CAND_ID':'VARCHAR',
        'TRAN_ID':'VARCHAR',
        'FILE_NUM':'VARCHAR',
        'MEMO_CD':'VARCHAR',
        'MEMO_TEXT':'VARCHAR',
        'SUB_ID':'VARCHAR'
    }
);

INSERT INTO etl.load_history
SELECT
    COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1) AS load_id,
    $Cycle,
    '$table',
    '$zipPathSql',
    $entryNameHistorySql,
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }
        elseif ($table -eq 'oppexp') {
            $loadSql = @"
LOAD zipfs;
DROP TABLE IF EXISTS $targetTable;
CREATE TABLE $targetTable AS
SELECT
    CMTE_ID,
    AMNDT_IND,
    TRY_CAST(NULLIF(TRIM(RPT_YR), '') AS SMALLINT) AS RPT_YR,
    RPT_TP,
    IMAGE_NUM,
    LINE_NUM,
    FORM_TP_CD,
    SCHED_TP_CD,
    NAME,
    CITY,
    STATE,
    ZIP_CODE,
    CAST(TRY_STRPTIME(NULLIF(TRIM(TRANSACTION_DT), ''), '%m%d%Y') AS DATE) AS TRANSACTION_DT,
    TRY_CAST(NULLIF(TRIM(TRANSACTION_AMT), '') AS DECIMAL(14,2)) AS TRANSACTION_AMT,
    TRANSACTION_PGI,
    PURPOSE,
    CATEGORY,
    CATEGORY_DESC,
    MEMO_CD,
    MEMO_TEXT,
    ENTITY_TP,
    TRY_CAST(NULLIF(TRIM(SUB_ID), '') AS BIGINT) AS SUB_ID,
    TRY_CAST(NULLIF(TRIM(FILE_NUM), '') AS BIGINT) AS FILE_NUM,
    TRAN_ID,
    BACK_REF_TRAN_ID
FROM read_csv(
    '$sourcePathSql',
    delim='|',
    header=false,
    all_varchar=true,
    null_padding=true,
    ignore_errors=true,
    sample_size=-1,
    columns={
        'CMTE_ID':'VARCHAR',
        'AMNDT_IND':'VARCHAR',
        'RPT_YR':'VARCHAR',
        'RPT_TP':'VARCHAR',
        'IMAGE_NUM':'VARCHAR',
        'LINE_NUM':'VARCHAR',
        'FORM_TP_CD':'VARCHAR',
        'SCHED_TP_CD':'VARCHAR',
        'NAME':'VARCHAR',
        'CITY':'VARCHAR',
        'STATE':'VARCHAR',
        'ZIP_CODE':'VARCHAR',
        'TRANSACTION_DT':'VARCHAR',
        'TRANSACTION_AMT':'VARCHAR',
        'TRANSACTION_PGI':'VARCHAR',
        'PURPOSE':'VARCHAR',
        'CATEGORY':'VARCHAR',
        'CATEGORY_DESC':'VARCHAR',
        'MEMO_CD':'VARCHAR',
        'MEMO_TEXT':'VARCHAR',
        'ENTITY_TP':'VARCHAR',
        'SUB_ID':'VARCHAR',
        'FILE_NUM':'VARCHAR',
        'TRAN_ID':'VARCHAR',
        'BACK_REF_TRAN_ID':'VARCHAR'
    }
);

INSERT INTO etl.load_history
SELECT
    COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1) AS load_id,
    $Cycle,
    '$table',
    '$zipPathSql',
    $entryNameHistorySql,
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }
        elseif ($table -eq 'weball') {
            $loadSql = @"
LOAD zipfs;
DROP TABLE IF EXISTS $targetTable;
CREATE TABLE $targetTable AS
SELECT
    CAND_ID,
    CAND_NAME,
    CAND_ICI,
    PTY_CD,
    CAND_PTY_AFFILIATION,
    TRY_CAST(NULLIF(TRIM(TTL_RECEIPTS), '') AS DECIMAL(14,2)) AS TTL_RECEIPTS,
    TRY_CAST(NULLIF(TRIM(TRANS_FROM_AUTH), '') AS DECIMAL(14,2)) AS TRANS_FROM_AUTH,
    TRY_CAST(NULLIF(TRIM(TTL_DISB), '') AS DECIMAL(14,2)) AS TTL_DISB,
    TRY_CAST(NULLIF(TRIM(TRANS_TO_AUTH), '') AS DECIMAL(14,2)) AS TRANS_TO_AUTH,
    TRY_CAST(NULLIF(TRIM(COH_BOP), '') AS DECIMAL(14,2)) AS COH_BOP,
    TRY_CAST(NULLIF(TRIM(COH_COP), '') AS DECIMAL(14,2)) AS COH_COP,
    TRY_CAST(NULLIF(TRIM(CAND_CONTRIB), '') AS DECIMAL(14,2)) AS CAND_CONTRIB,
    TRY_CAST(NULLIF(TRIM(CAND_LOANS), '') AS DECIMAL(14,2)) AS CAND_LOANS,
    TRY_CAST(NULLIF(TRIM(OTHER_LOANS), '') AS DECIMAL(14,2)) AS OTHER_LOANS,
    TRY_CAST(NULLIF(TRIM(CAND_LOAN_REPAY), '') AS DECIMAL(14,2)) AS CAND_LOAN_REPAY,
    TRY_CAST(NULLIF(TRIM(OTHER_LOAN_REPAY), '') AS DECIMAL(14,2)) AS OTHER_LOAN_REPAY,
    TRY_CAST(NULLIF(TRIM(DEBTS_OWED_BY), '') AS DECIMAL(14,2)) AS DEBTS_OWED_BY,
    TRY_CAST(NULLIF(TRIM(TTL_INDIV_CONTRIB), '') AS DECIMAL(14,2)) AS TTL_INDIV_CONTRIB,
    CAND_OFFICE_ST,
    CAND_OFFICE_DISTRICT,
    SPEC_ELECTION,
    PRIM_ELECTION,
    RUN_ELECTION,
    GEN_ELECTION,
    TRY_CAST(NULLIF(TRIM(GEN_ELECTION_PRECENT), '') AS DECIMAL(7,4)) AS GEN_ELECTION_PRECENT,
    TRY_CAST(NULLIF(TRIM(OTHER_POL_CMTE_CONTRIB), '') AS DECIMAL(14,2)) AS OTHER_POL_CMTE_CONTRIB,
    TRY_CAST(NULLIF(TRIM(POL_PTY_CONTRIB), '') AS DECIMAL(14,2)) AS POL_PTY_CONTRIB,
    COALESCE(
        CAST(TRY_STRPTIME(NULLIF(TRIM(CVG_END_DT), ''), '%m/%d/%Y') AS DATE),
        CAST(TRY_STRPTIME(NULLIF(TRIM(CVG_END_DT), ''), '%m%d%Y') AS DATE)
    ) AS CVG_END_DT,
    TRY_CAST(NULLIF(TRIM(INDIV_REFUNDS), '') AS DECIMAL(14,2)) AS INDIV_REFUNDS,
    TRY_CAST(NULLIF(TRIM(CMTE_REFUNDS), '') AS DECIMAL(14,2)) AS CMTE_REFUNDS
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
        'CAND_ICI':'VARCHAR',
        'PTY_CD':'VARCHAR',
        'CAND_PTY_AFFILIATION':'VARCHAR',
        'TTL_RECEIPTS':'VARCHAR',
        'TRANS_FROM_AUTH':'VARCHAR',
        'TTL_DISB':'VARCHAR',
        'TRANS_TO_AUTH':'VARCHAR',
        'COH_BOP':'VARCHAR',
        'COH_COP':'VARCHAR',
        'CAND_CONTRIB':'VARCHAR',
        'CAND_LOANS':'VARCHAR',
        'OTHER_LOANS':'VARCHAR',
        'CAND_LOAN_REPAY':'VARCHAR',
        'OTHER_LOAN_REPAY':'VARCHAR',
        'DEBTS_OWED_BY':'VARCHAR',
        'TTL_INDIV_CONTRIB':'VARCHAR',
        'CAND_OFFICE_ST':'VARCHAR',
        'CAND_OFFICE_DISTRICT':'VARCHAR',
        'SPEC_ELECTION':'VARCHAR',
        'PRIM_ELECTION':'VARCHAR',
        'RUN_ELECTION':'VARCHAR',
        'GEN_ELECTION':'VARCHAR',
        'GEN_ELECTION_PRECENT':'VARCHAR',
        'OTHER_POL_CMTE_CONTRIB':'VARCHAR',
        'POL_PTY_CONTRIB':'VARCHAR',
        'CVG_END_DT':'VARCHAR',
        'INDIV_REFUNDS':'VARCHAR',
        'CMTE_REFUNDS':'VARCHAR'
    }
);

INSERT INTO etl.load_history
SELECT
    COALESCE((SELECT MAX(load_id) + 1 FROM etl.load_history), 1) AS load_id,
    $Cycle,
    '$table',
    '$zipPathSql',
    $entryNameHistorySql,
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }
        else {
            $loadSql = @"
LOAD zipfs;
DROP TABLE IF EXISTS $targetTable;
CREATE TABLE $targetTable AS
SELECT
    *
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
    $entryNameHistorySql,
    '$targetTable',
    (SELECT COUNT(*) FROM $targetTable),
    NOW();
"@
        }

        duckdb $dbPathResolved -c $loadSql
        if ($LASTEXITCODE -ne 0) {
            if ($table -eq 'indiv') {
                throw "DuckDB load failed for $zipName. This archive may contain multiple files; use extraction or explicit-entry handling for indiv."
            }

            throw "DuckDB load failed for $zipName"
        }

        $loadedCount++
        Write-Host "[$index/$total] Loaded $zipName into $targetTable"
        Write-Verbose "LOADED  $zipName -> $targetTable"
    }
    catch {
        $failedCount++
        Write-Error "Failed loading ${zipName}: $_"
        throw
    }
}

Write-Progress -Id 1 -Activity "Loading FEC tables for cycle $Cycle" -Completed
Write-Host "Load summary for ${Cycle}: loaded $loadedCount, skipped $skippedCount, failed $failedCount, total $total."

if ($failedCount -gt 0) {
    exit 1
}
