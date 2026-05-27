[CmdletBinding()]
param(
    [Parameter(Position = 0, HelpMessage = 'Election cycle year (e.g. 2026)')]
    [string]$Cycle = '2026',
    [Parameter(
        Position = 1,
        ValueFromRemainingArguments = $true,
        HelpMessage = 'Table names without cycle suffix (e.g. indiv, weball).'
    )]
    [string[]]$Tables,
    [Parameter(HelpMessage = 'Force download even when local file and signature match.')]
    [switch]$Force,
    [Parameter(HelpMessage = 'Maximum number of concurrent downloads.')]
    [ValidateRange(1, 16)]
    [int]$Parallelism = 4,
    [Parameter(HelpMessage = 'Path to the DuckDB database file used for provenance logging.')]
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

if (-not $Cycle) {
    Write-Error (
        'Usage: .\scripts\fetch-bulk.ps1 <cycle> [table1,table2,...] [-Force] [-Parallelism N]`n' +
        '  e.g. .\scripts\fetch-bulk.ps1 2026 indiv,weball -Force -Parallelism 4'
    )
    exit 1
}

if ($Cycle -notmatch '^\d{4}$') {
    Write-Error 'Cycle must be a four-digit election year, e.g. 2026.'
    exit 1
}

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

    if ($Tables.Count -eq 0) {
        Write-Error 'Tables parameter is empty. Provide comma-separated table names such as indiv,weball.'
        exit 1
    }
}

$invalidTables = @($Tables | Where-Object { $_ -notin $defaultTables })
if ($invalidTables.Count -gt 0) {
    Write-Error "Unknown table name(s): $($invalidTables -join ', '). Valid tables: $($defaultTables -join ', ')."
    exit 1
}

function Format-ProgressStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    return "[ $Text ]"
}

function New-ProgressBarLine {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Percent,
        [int]$Width = 22
    )

    $boundedPercent = [Math]::Max(0, [Math]::Min(100, $Percent))
    $filled = [int][Math]::Round(($boundedPercent / 100.0) * $Width)
    if ($filled -gt $Width) {
        $filled = $Width
    }
    $empty = $Width - $filled

    return ('[' + ('#' * $filled) + (' ' * $empty) + ']')
}

function Get-CurlHeaderMap {
    param(
        [Parameter(Mandatory = $true)]
        [string]$HeaderPath
    )

    $latestHeaders = @{}
    if (-not (Test-Path -Path $HeaderPath -PathType Leaf)) {
        return $latestHeaders
    }

    $currentHeaders = @{}
    $headerLines = Get-Content -Path $HeaderPath
    foreach ($line in $headerLines) {
        if ($line -match '^HTTP/\d+(?:\.\d+)?\s+\d+') {
            if ($currentHeaders.Count -gt 0) {
                $latestHeaders = $currentHeaders
            }
            $currentHeaders = @{}
            continue
        }

        if ([string]::IsNullOrWhiteSpace($line)) {
            if ($currentHeaders.Count -gt 0) {
                $latestHeaders = $currentHeaders
            }
            continue
        }

        $separatorIndex = $line.IndexOf(':')
        if ($separatorIndex -le 0) {
            continue
        }

        $headerName = $line.Substring(0, $separatorIndex).Trim().ToLowerInvariant()
        $headerValue = $line.Substring($separatorIndex + 1).Trim()
        $currentHeaders[$headerName] = $headerValue
    }

    if ($currentHeaders.Count -gt 0) {
        $latestHeaders = $currentHeaders
    }

    return $latestHeaders
}

function To-SqlStringOrNull {
    param(
        [AllowNull()]
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return 'NULL'
    }

    return "'$($Value.Replace("'", "''"))'"
}

function To-SqlBigIntOrNull {
    param(
        [AllowNull()]
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return 'NULL'
    }

    $parsedValue = [int64]0
    if ([int64]::TryParse($Value, [ref]$parsedValue)) {
        return $parsedValue.ToString()
    }

    return 'NULL'
}

function To-SqlIntOrNull {
    param(
        [AllowNull()]
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return 'NULL'
    }

    $parsedValue = [int]0
    if ([int]::TryParse($Value, [ref]$parsedValue)) {
        return $parsedValue.ToString()
    }

    return 'NULL'
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$yy = $Cycle.Substring(2)
$baseUrl = "https://www.fec.gov/files/bulk-downloads/$Cycle"
$destDir = Join-Path $repoRoot "data\$Cycle"
$dbPathResolved = if ([System.IO.Path]::IsPathRooted($DbPath)) { $DbPath } else { Join-Path $repoRoot $DbPath }
$schemaSqlPath = Join-Path $repoRoot 'sql\schema\001_create_fec_schemas.sql'

$files = @($Tables | ForEach-Object { "$($_)$yy" })

New-Item -ItemType Directory -Path $destDir -Force | Out-Null
New-Item -ItemType Directory -Path (Split-Path -Parent $dbPathResolved) -Force | Out-Null

if (-not (Test-Path -Path $schemaSqlPath -PathType Leaf)) {
    Write-Error "Schema SQL not found: $schemaSqlPath"
    exit 1
}

$initCommand = ".read '$($schemaSqlPath.Replace('\\', '/'))'"
duckdb $dbPathResolved -c $initCommand
if ($LASTEXITCODE -ne 0) {
    Write-Error 'Failed to initialize DuckDB schema objects for fetch provenance.'
    exit 1
}

Write-Host "Downloading FEC bulk data - cycle $Cycle"
Write-Host "Tables: $($Tables -join ', ')"
Write-Host "Destination: $destDir"
Write-Host "Parallelism: $Parallelism"
Write-Host ''

$progressId = 1
$totalFiles = $files.Count
$currentFile = 0
$downloadedCount = 0
$skippedCount = 0
$failedCount = 0
$downloadPlans = @()
$statusMap = [System.Collections.Concurrent.ConcurrentDictionary[string, string]]::new()
$bytesMap = [System.Collections.Concurrent.ConcurrentDictionary[string, int64]]::new()
$totalMap = [System.Collections.Concurrent.ConcurrentDictionary[string, int64]]::new()
$tableProgressIds = @{}

for ($i = 0; $i -lt $files.Count; $i++) {
    $tableName = $files[$i]
    $tableProgressIds[$tableName] = 100 + $i
    [void]$statusMap.TryAdd($tableName, 'Pending')
    [void]$bytesMap.TryAdd($tableName, 0)
    [void]$totalMap.TryAdd($tableName, 0)
}

if ($totalFiles -eq 0) {
    Write-Warning 'No tables selected. Nothing to download.'
    exit 0
}

Push-Location $repoRoot

try {
    foreach ($name in $files) {
        try {
            $currentFile++
            $zipPath = Join-Path $destDir "$name.zip"
            $tableName = if ($name.EndsWith($yy)) { $name.Substring(0, $name.Length - $yy.Length) } else { $name }

            $url = "$baseUrl/$name.zip"
            $metaPath = Join-Path $destDir ".$name.meta"

            Write-Progress `
                -Id $progressId `
                -Activity "Preparing FEC bulk downloads ($Cycle)" `
                -Status (Format-ProgressStatus "queueing $name.zip ($currentFile/$totalFiles)") `
                -PercentComplete ([int]($currentFile * 100 / $totalFiles))

            $downloadPlans += [PSCustomObject]@{
                Name = $name
                TableName = $tableName
                Url = $url
                ZipPath = $zipPath
                MetaPath = $metaPath
                StatusPath = Join-Path $repoRoot ("tmp\\{0}.curl.status" -f $name)
                ErrorPath = Join-Path $repoRoot ("tmp\\{0}.curl.err" -f $name)
                HeaderPath = Join-Path $repoRoot ("tmp\\{0}.curl.headers" -f $name)
            }
            $statusMap[$name] = 'Queued'
            Write-Progress `
                -Id $progressId `
                -Activity "Preparing FEC bulk downloads ($Cycle)" `
                -Status (Format-ProgressStatus "queued $name.zip") `
                -PercentComplete ([int]($currentFile * 100 / $totalFiles))
        }
        catch {
            $failedCount++
            Write-Verbose "FAILED  $name.zip"
            throw
        }
    }

    Write-Progress -Id $progressId -Activity "Preparing FEC bulk downloads ($Cycle)" -Completed

    if ($downloadPlans.Count -gt 0) {
        Write-Host "Starting $($downloadPlans.Count) download(s) in parallel..."

        # Parallel scheduler: keep a queue of pending plans and a list of active curl processes.
        # The inner loop launches up to -Parallelism workers; the outer loop monitors completion.
        $pendingPlans = [System.Collections.Generic.Queue[object]]::new()
        foreach ($plan in $downloadPlans) {
            $pendingPlans.Enqueue($plan)
        }

        $activeJobs = @()
        $downloadResults = @()
        $parallelParentProgressId = 10

        while (($pendingPlans.Count -gt 0) -or ($activeJobs.Count -gt 0)) {
            while (($activeJobs.Count -lt $Parallelism) -and ($pendingPlans.Count -gt 0)) {
                $nextPlan = $pendingPlans.Dequeue()
                $destinationDir = Split-Path -Parent $nextPlan.ZipPath
                if ($destinationDir) {
                    New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
                }

                New-Item -ItemType Directory -Path (Split-Path -Parent $nextPlan.StatusPath) -Force | Out-Null
                if (Test-Path $nextPlan.StatusPath) {
                    Remove-Item -Path $nextPlan.StatusPath -Force
                }
                if (Test-Path $nextPlan.ErrorPath) {
                    Remove-Item -Path $nextPlan.ErrorPath -Force
                }
                if (Test-Path $nextPlan.HeaderPath) {
                    Remove-Item -Path $nextPlan.HeaderPath -Force
                }

                $statusMap[$nextPlan.Name] = 'Downloading'
                $bytesMap[$nextPlan.Name] = 0
                $totalMap[$nextPlan.Name] = 0

                $curlArgs = @(
                    '-L',
                    '--fail',
                    '--silent',
                    '--show-error',
                    '--write-out', '%{http_code}|%{size_download}|%{size_upload}',
                    '--dump-header', $nextPlan.HeaderPath,
                    '--etag-save', $nextPlan.MetaPath,
                    '--output', $nextPlan.ZipPath,
                    $nextPlan.Url
                )

                if ((-not $Force) -and (Test-Path $nextPlan.MetaPath)) {
                    $curlArgs = @('--etag-compare', $nextPlan.MetaPath) + $curlArgs
                }

                $proc = Start-Process `
                    -FilePath 'curl.exe' `
                    -ArgumentList $curlArgs `
                    -NoNewWindow `
                    -PassThru `
                    -RedirectStandardOutput $nextPlan.StatusPath `
                    -RedirectStandardError $nextPlan.ErrorPath
                $activeJobs += [PSCustomObject]@{
                    Process = $proc
                    Plan = $nextPlan
                }
            }

            # Progress source for active downloads: poll current zip file size on disk.
            foreach ($activeItem in $activeJobs) {
                if (Test-Path $activeItem.Plan.ZipPath) {
                    $bytesMap[$activeItem.Plan.Name] = (Get-Item -Path $activeItem.Plan.ZipPath).Length
                }
            }

            $completedItems = @($activeJobs | Where-Object { $_.Process.HasExited })
            foreach ($completedItem in $completedItems) {
                $httpCode = ''
                $sizeDownload = ''
                $headers = Get-CurlHeaderMap -HeaderPath $completedItem.Plan.HeaderPath
                $etag = if ($headers.ContainsKey('etag')) { $headers['etag'] } else { '' }
                $responseDate = if ($headers.ContainsKey('date')) { $headers['date'] } else { '' }
                $lastModified = if ($headers.ContainsKey('last-modified')) { $headers['last-modified'] } else { '' }
                $contentLength = if ($headers.ContainsKey('content-length')) { $headers['content-length'] } else { '' }

                if ($completedItem.Process.ExitCode -eq 0) {
                    $writeOut = ''
                    if (Test-Path $completedItem.Plan.StatusPath) {
                        $writeOut = (Get-Content -Path $completedItem.Plan.StatusPath -Raw).Trim()
                    }

                    if ($writeOut) {
                        $writeOutParts = $writeOut.Split('|')
                        if ($writeOutParts.Count -ge 1) {
                            $httpCode = $writeOutParts[0]
                        }
                        if ($writeOutParts.Count -ge 2) {
                            $sizeDownload = $writeOutParts[1]
                        }
                    }

                    if ([string]::IsNullOrWhiteSpace($contentLength)) {
                        $contentLength = $sizeDownload
                    }

                    $localFileSize = ''
                    if (Test-Path -Path $completedItem.Plan.ZipPath -PathType Leaf) {
                        $localFileSize = (Get-Item -Path $completedItem.Plan.ZipPath).Length.ToString()
                    }

                    if ($httpCode -eq '304') {
                        $statusMap[$completedItem.Plan.Name] = 'Skipped'
                        $downloadResults += [PSCustomObject]@{
                            Name = $completedItem.Plan.Name
                            TableName = $completedItem.Plan.TableName
                            ZipName = "$($completedItem.Plan.Name).zip"
                            Url = $completedItem.Plan.Url
                            Status = 'Skipped'
                            HttpStatus = $httpCode
                            ContentLength = $contentLength
                            ResponseDate = $responseDate
                            LastModified = $lastModified
                            ETag = $etag
                            LocalFileSize = $localFileSize
                            Error = ''
                        }
                    }
                    else {
                        $statusMap[$completedItem.Plan.Name] = 'Completed'
                        $downloadResults += [PSCustomObject]@{
                            Name = $completedItem.Plan.Name
                            TableName = $completedItem.Plan.TableName
                            ZipName = "$($completedItem.Plan.Name).zip"
                            Url = $completedItem.Plan.Url
                            Status = 'Completed'
                            HttpStatus = $httpCode
                            ContentLength = $contentLength
                            ResponseDate = $responseDate
                            LastModified = $lastModified
                            ETag = $etag
                            LocalFileSize = $localFileSize
                            Error = ''
                        }
                    }
                }
                else {
                    $statusMap[$completedItem.Plan.Name] = 'Failed'
                    $curlError = "curl exited with code $($completedItem.Process.ExitCode)"
                    if (Test-Path $completedItem.Plan.ErrorPath) {
                        $stderrText = (Get-Content -Path $completedItem.Plan.ErrorPath -Raw).Trim()
                        if ($stderrText) {
                            $curlError = "${curlError}: $stderrText"
                        }
                    }

                    $downloadResults += [PSCustomObject]@{
                        Name = $completedItem.Plan.Name
                        TableName = $completedItem.Plan.TableName
                        ZipName = "$($completedItem.Plan.Name).zip"
                        Url = $completedItem.Plan.Url
                        Status = 'Failed'
                        HttpStatus = $httpCode
                        ContentLength = $contentLength
                        ResponseDate = $responseDate
                        LastModified = $lastModified
                        ETag = $etag
                        LocalFileSize = ''
                        Error = $curlError
                    }
                }

                if (Test-Path $completedItem.Plan.StatusPath) {
                    Remove-Item -Path $completedItem.Plan.StatusPath -Force
                }
                if (Test-Path $completedItem.Plan.ErrorPath) {
                    Remove-Item -Path $completedItem.Plan.ErrorPath -Force
                }
                if (Test-Path $completedItem.Plan.HeaderPath) {
                    Remove-Item -Path $completedItem.Plan.HeaderPath -Force
                }
            }

            if ($completedItems.Count -gt 0) {
                $activeJobs = @($activeJobs | Where-Object { -not $_.Process.HasExited })
            }

            $doneCount = $downloadResults.Count
            $queueTotal = $downloadPlans.Count
            # Parent progress bar reflects overall completion across all requested tables.
            Write-Progress `
                -Id $parallelParentProgressId `
                -Activity "Downloading FEC bulk data ($Cycle)" `
                -Status (Format-ProgressStatus "$doneCount / $queueTotal completed") `
                -PercentComplete ([int](($doneCount * 100) / $queueTotal))

            # Child progress bars render one row per table using statusMap + bytesMap snapshots.
            foreach ($tableName in $files) {
                $tableProgressId = $tableProgressIds[$tableName]
                $tableStatus = 'Pending'
                if ($statusMap.ContainsKey($tableName)) {
                    $tableStatus = $statusMap[$tableName]
                }

                $tableBytes = [int64]0
                if ($bytesMap.ContainsKey($tableName)) {
                    $tableBytes = $bytesMap[$tableName]
                }

                $tableTotal = [int64]0
                if ($totalMap.ContainsKey($tableName)) {
                    $tableTotal = $totalMap[$tableName]
                }

                if ($tableStatus -eq 'Downloading') {
                    if ($tableTotal -gt 0) {
                        $percent = [int](($tableBytes * 100) / $tableTotal)
                        Write-Progress `
                            -Id $tableProgressId `
                            -ParentId $parallelParentProgressId `
                            -Activity "$tableName.zip" `
                            -Status (Format-ProgressStatus (
                                "{0:N1} MB / {1:N1} MB" -f ($tableBytes / 1MB), ($tableTotal / 1MB)
                            )) `
                            -PercentComplete $percent
                    }
                    else {
                        Write-Progress `
                            -Id $tableProgressId `
                            -ParentId $parallelParentProgressId `
                            -Activity "$tableName.zip" `
                            -Status (Format-ProgressStatus (
                                "{0:N1} MB downloaded" -f ($tableBytes / 1MB)
                            ))
                    }
                }
                elseif ($tableStatus -eq 'Queued' -or $tableStatus -eq 'Pending') {
                    Write-Progress `
                        -Id $tableProgressId `
                        -ParentId $parallelParentProgressId `
                        -Activity "$tableName.zip" `
                        -Status (Format-ProgressStatus 'queued') `
                        -PercentComplete 0
                }
                elseif ($tableStatus -eq 'Skipped') {
                    Write-Progress `
                        -Id $tableProgressId `
                        -ParentId $parallelParentProgressId `
                        -Activity "$tableName.zip" `
                        -Status (Format-ProgressStatus 'skipped (unchanged)') `
                        -PercentComplete 100
                }
                elseif ($tableStatus -eq 'Completed') {
                    Write-Progress `
                        -Id $tableProgressId `
                        -ParentId $parallelParentProgressId `
                        -Activity "$tableName.zip" `
                        -Status (Format-ProgressStatus 'completed') `
                        -PercentComplete 100
                }
                else {
                    Write-Progress `
                        -Id $tableProgressId `
                        -ParentId $parallelParentProgressId `
                        -Activity "$tableName.zip" `
                        -Status (Format-ProgressStatus 'failed') `
                        -PercentComplete 100
                }
            }

            if ($activeJobs.Count -gt 0) {
                $activeProcessIds = @(
                    $activeJobs |
                        Where-Object { $_.Process -and (-not $_.Process.HasExited) -and $_.Process.Id } |
                        ForEach-Object { $_.Process.Id }
                )

                if ($activeProcessIds.Count -gt 0) {
                    Wait-Process -Id $activeProcessIds -Timeout 1 -ErrorAction SilentlyContinue
                }
            }
        }

        Write-Progress `
            -Id $parallelParentProgressId `
            -Activity "Downloading FEC bulk data ($Cycle)" `
            -Status (Format-ProgressStatus "$($downloadResults.Count) / $($downloadPlans.Count) completed") `
            -PercentComplete 100

        foreach ($result in $downloadResults) {
            $insertFetchSql = @"
INSERT INTO etl.fetch_history
SELECT
    COALESCE((SELECT MAX(fetch_id) + 1 FROM etl.fetch_history), 1) AS fetch_id,
    $Cycle,
    $(To-SqlStringOrNull -Value $result.TableName),
    $(To-SqlStringOrNull -Value $result.ZipName),
    $(To-SqlStringOrNull -Value $result.Url),
    $(To-SqlStringOrNull -Value $result.Status),
    $(To-SqlIntOrNull -Value $result.HttpStatus),
    $(To-SqlBigIntOrNull -Value $result.ContentLength),
    $(To-SqlStringOrNull -Value $result.ResponseDate),
    $(To-SqlStringOrNull -Value $result.LastModified),
    $(To-SqlStringOrNull -Value $result.ETag),
    $(To-SqlBigIntOrNull -Value $result.LocalFileSize),
    NOW() AS fetched_at,
    $(To-SqlStringOrNull -Value $result.Error);
"@

            duckdb $dbPathResolved -c $insertFetchSql
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Failed writing fetch provenance for $($result.Name).zip"
                exit 1
            }

                        $qualityStatus = if ($result.Status -eq 'Completed' -or $result.Status -eq 'Skipped') { 'pass' } elseif ($result.Status -eq 'Failed') { 'error' } else { 'unknown' }
                        $upsertCurrentStateSql = @"
DELETE FROM etl.current_state
WHERE entity_type = 'file'
    AND cycle = $Cycle
    AND entity_name = $(To-SqlStringOrNull -Value $result.ZipName);

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
        'file' AS entity_type,
        $Cycle AS cycle,
        $(To-SqlStringOrNull -Value $result.TableName) AS table_name,
        $(To-SqlStringOrNull -Value $result.ZipName) AS entity_name,
        'fetch' AS last_operation,
        $(To-SqlStringOrNull -Value $result.Status) AS operation_status,
        '$qualityStatus' AS quality_status,
        $(To-SqlStringOrNull -Value $result.Url) AS source_url,
        NULL AS source_zip_path,
        NULL AS source_entry_name,
        NULL AS target_table_name,
        $(To-SqlIntOrNull -Value $result.HttpStatus) AS http_status,
        $(To-SqlBigIntOrNull -Value $result.ContentLength) AS content_length,
        NULL AS row_count,
        NULL AS duration_ms,
        $(To-SqlStringOrNull -Value $result.ResponseDate) AS response_date,
        $(To-SqlStringOrNull -Value $result.LastModified) AS last_modified,
        $(To-SqlStringOrNull -Value $result.ETag) AS etag,
        $(To-SqlStringOrNull -Value $result.Error) AS error_text,
        NOW() AS updated_at;
"@

            duckdb $dbPathResolved -c $upsertCurrentStateSql
            if ($LASTEXITCODE -ne 0) {
                Write-Error "Failed writing current file state for $($result.Name).zip"
                exit 1
            }

            if ($result.Status -eq 'Completed') {
                $downloadedCount++
                Write-Verbose "COMPLETED  $($result.Name).zip"
            }
            elseif ($result.Status -eq 'Skipped') {
                $skippedCount++
                Write-Verbose "SKIPPED  $($result.Name).zip"
            }
            else {
                $failedCount++
                Write-Verbose "FAILED  $($result.Name).zip : $($result.Error)"
            }
        }

        if ($failedCount -gt 0) {
            Write-Error "$failedCount download(s) failed. Re-run with -Verbose for details."
            exit 1
        }
    }

    Write-Host (
        "Completed cycle ${Cycle}: completed $downloadedCount, skipped $skippedCount, " +
        "failed $failedCount, total $totalFiles."
    )
    Write-Host ''
    Write-Host 'Final table status bars (persistent):'
    # Write-Progress UI is transient in some hosts; print a static summary so results remain visible.
    foreach ($tableName in $files) {
        $finalStatus = 'pending'
        if ($statusMap.ContainsKey($tableName)) {
            $finalStatus = $statusMap[$tableName].ToLowerInvariant()
        }

        $finalPercent = 0
        if ($finalStatus -eq 'completed' -or $finalStatus -eq 'skipped' -or $finalStatus -eq 'failed') {
            $finalPercent = 100
        }

        $bar = New-ProgressBarLine -Percent $finalPercent -Width 22
        $statusLabel = Format-ProgressStatus $finalStatus
        Write-Host ("{0,-12} {1} {2,4}%  {3}" -f "$tableName.zip", $bar, $finalPercent, $statusLabel)
    }
}
finally {
    Pop-Location
}
