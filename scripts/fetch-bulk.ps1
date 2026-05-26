[CmdletBinding()]
param(
    [Parameter(Position = 0, HelpMessage = 'Election cycle year (e.g. 2026)')]
    [string]$Cycle = '2026',
    [Parameter(Position = 1, ValueFromRemainingArguments = $true, HelpMessage = 'Table names without cycle suffix (e.g. indiv, weball).')]
    [string[]]$Tables,
    [Parameter(HelpMessage = 'Force download even when local file and signature match.')]
    [switch]$Force,
    [Parameter(HelpMessage = 'Maximum number of concurrent downloads.')]
    [ValidateRange(1, 16)]
    [int]$Parallelism = 4
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

if (-not $Cycle) {
    Write-Error 'Usage: .\scripts\fetch-bulk.ps1 <cycle> [table1 table2 ...] [-Force] [-Parallelism N]`n  e.g. .\scripts\fetch-bulk.ps1 2026 indiv weball -Force -Parallelism 4'
    exit 1
}

if ($Cycle -notmatch '^\d{4}$') {
    Write-Error 'Cycle must be a four-digit election year, e.g. 2026.'
    exit 1
}

if (-not $Tables -or $Tables.Count -eq 0) {
    $Tables = $defaultTables
}

function Get-RemoteSignature {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url
    )

    $response = Invoke-WebRequest -Uri $Url -Method Head -MaximumRedirection 10
    $etag = [string]$response.Headers['ETag']
    $lastModified = [string]$response.Headers['Last-Modified']
    $contentLength = [string]$response.Headers['Content-Length']

    return "$etag|$lastModified|$contentLength"
}

function Save-File {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [Parameter(Mandatory = $true)]
        [string]$Destination,
        [Parameter(Mandatory = $true)]
        [int]$ProgressId,
        [Parameter(Mandatory = $true)]
        [string]$Activity
    )

    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $true
    $client = [System.Net.Http.HttpClient]::new($handler)
    $request = $null
    $response = $null
    $responseStream = $null
    $fileStream = $null

    try {
        $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $Url)
        $response = $client.Send($request, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead)
        [void]$response.EnsureSuccessStatusCode()

        $totalBytes = $response.Content.Headers.ContentLength
        $responseStream = $response.Content.ReadAsStream()

        $destinationDir = Split-Path -Parent $Destination
        if ($destinationDir) {
            New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
        }

        $fileStream = [System.IO.File]::Open($Destination, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        $buffer = New-Object byte[] (128KB)
        $totalRead = [int64]0

        while (($bytesRead = $responseStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $fileStream.Write($buffer, 0, $bytesRead)
            $totalRead += $bytesRead

            if ($totalBytes -and $totalBytes -gt 0) {
                $percent = [int](($totalRead * 100) / $totalBytes)
                Write-Progress -Id $ProgressId -Activity $Activity -Status ("{0:N1} MB / {1:N1} MB" -f ($totalRead / 1MB), ($totalBytes / 1MB)) -PercentComplete $percent
            }
            else {
                Write-Progress -Id $ProgressId -Activity $Activity -Status ("{0:N1} MB downloaded" -f ($totalRead / 1MB))
            }
        }
    }
    finally {
        if ($fileStream) {
            $fileStream.Dispose()
        }

        if ($responseStream) {
            $responseStream.Dispose()
        }

        if ($response) {
            $response.Dispose()
        }

        if ($request) {
            $request.Dispose()
        }

        $client.Dispose()
        $handler.Dispose()
        Write-Progress -Id $ProgressId -Activity $Activity -Completed
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$yy = $Cycle.Substring(2)
$baseUrl = "https://www.fec.gov/files/bulk-downloads/$Cycle"
$destDir = Join-Path $repoRoot "data\$Cycle"

$files = $Tables | ForEach-Object { "$($_)$yy" }

New-Item -ItemType Directory -Path $destDir -Force | Out-Null

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
            $url = "$baseUrl/$name.zip"
            $metaPath = Join-Path $destDir ".$name.meta"

            Write-Progress -Id $progressId -Activity "Preparing FEC bulk downloads ($Cycle)" -Status "Checking $name.zip ($currentFile/$totalFiles)" -PercentComplete ([int](($currentFile - 1) * 100 / $totalFiles))

            $remoteSignature = Get-RemoteSignature -Url $url
            $previousSignature = ''

            if (Test-Path $metaPath) {
                $previousSignature = (Get-Content -Path $metaPath -Raw).Trim()
            }

            if ((-not $Force) -and (Test-Path $zipPath) -and $previousSignature -and ($remoteSignature -eq $previousSignature)) {
                Write-Progress -Id $progressId -Activity "Preparing FEC bulk downloads ($Cycle)" -Status "Skipped $name.zip (unchanged)" -PercentComplete ([int]($currentFile * 100 / $totalFiles))
                Write-Verbose "SKIPPED  $name.zip"
                $skippedCount++
                $statusMap[$name] = 'Skipped'
                $bytesMap[$name] = 0
                $totalMap[$name] = 0
                continue
            }

            $downloadPlans += [PSCustomObject]@{
                Name = $name
                Url = $url
                ZipPath = $zipPath
                MetaPath = $metaPath
                RemoteSignature = $remoteSignature
            }
            $statusMap[$name] = 'Queued'
            Write-Progress -Id $progressId -Activity "Preparing FEC bulk downloads ($Cycle)" -Status "Queued $name.zip" -PercentComplete ([int]($currentFile * 100 / $totalFiles))
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

        $pendingPlans = [System.Collections.Generic.Queue[object]]::new()
        foreach ($plan in $downloadPlans) {
            $pendingPlans.Enqueue($plan)
        }

        $activeJobs = @()
        $downloadResults = @()
        $parallelParentProgressId = 10
        $parallelChildProgressId = 11

        $downloadScript = {
            param($plan, $statusMap, $bytesMap, $totalMap)

            $handler = [System.Net.Http.HttpClientHandler]::new()
            $handler.AllowAutoRedirect = $true
            $client = [System.Net.Http.HttpClient]::new($handler)
            $request = $null
            $response = $null
            $responseStream = $null
            $fileStream = $null

            try {
                $statusMap[$plan.Name] = 'Downloading'
                $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, $plan.Url)
                $response = $client.Send($request, [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead)
                [void]$response.EnsureSuccessStatusCode()
                $contentLength = $response.Content.Headers.ContentLength
                if ($contentLength -and $contentLength -gt 0) {
                    $totalMap[$plan.Name] = [int64]$contentLength
                }
                $responseStream = $response.Content.ReadAsStream()

                $destinationDir = Split-Path -Parent $plan.ZipPath
                if ($destinationDir) {
                    New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
                }

                $fileStream = [System.IO.File]::Open($plan.ZipPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
                $buffer = New-Object byte[] (128KB)
                $totalRead = [int64]0
                while (($bytesRead = $responseStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $fileStream.Write($buffer, 0, $bytesRead)
                    $totalRead += $bytesRead
                    $bytesMap[$plan.Name] = $totalRead
                }

                Set-Content -Path $plan.MetaPath -Value $plan.RemoteSignature
                $statusMap[$plan.Name] = 'Downloaded'

                [PSCustomObject]@{
                    Name = $plan.Name
                    Status = 'Downloaded'
                    Error = ''
                }
            }
            catch {
                $statusMap[$plan.Name] = 'Failed'
                [PSCustomObject]@{
                    Name = $plan.Name
                    Status = 'Failed'
                    Error = $_.Exception.Message
                }
            }
            finally {
                if ($fileStream) {
                    $fileStream.Dispose()
                }

                if ($responseStream) {
                    $responseStream.Dispose()
                }

                if ($response) {
                    $response.Dispose()
                }

                if ($request) {
                    $request.Dispose()
                }

                $client.Dispose()
                $handler.Dispose()
            }
        }

        while (($pendingPlans.Count -gt 0) -or ($activeJobs.Count -gt 0)) {
            while (($activeJobs.Count -lt $Parallelism) -and ($pendingPlans.Count -gt 0)) {
                $nextPlan = $pendingPlans.Dequeue()
                $job = Start-ThreadJob -ScriptBlock $downloadScript -ArgumentList $nextPlan, $statusMap, $bytesMap, $totalMap
                $activeJobs += [PSCustomObject]@{
                    Job = $job
                    Name = $nextPlan.Name
                }
            }

            $completedItems = @($activeJobs | Where-Object { $_.Job.State -match 'Completed|Failed|Stopped' })
            foreach ($completedItem in $completedItems) {
                $result = Receive-Job -Job $completedItem.Job -Wait -AutoRemoveJob
                if ($result) {
                    $downloadResults += $result
                }
                else {
                    $downloadResults += [PSCustomObject]@{
                        Name = $completedItem.Name
                        Status = 'Failed'
                        Error = 'Download job ended without result.'
                    }
                }
            }

            if ($completedItems.Count -gt 0) {
                $activeJobs = @($activeJobs | Where-Object { $_.Job.State -notmatch 'Completed|Failed|Stopped' })
            }

            $doneCount = $downloadResults.Count
            $queueTotal = $downloadPlans.Count
            Write-Progress -Id $parallelParentProgressId -Activity "Downloading FEC bulk data ($Cycle)" -Status "$doneCount / $queueTotal completed" -PercentComplete ([int](($doneCount * 100) / $queueTotal))

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
                        Write-Progress -Id $tableProgressId -ParentId $parallelParentProgressId -Activity "$tableName.zip" -Status ("{0:N1} MB / {1:N1} MB" -f ($tableBytes / 1MB), ($tableTotal / 1MB)) -PercentComplete $percent
                    }
                    else {
                        Write-Progress -Id $tableProgressId -ParentId $parallelParentProgressId -Activity "$tableName.zip" -Status ("{0:N1} MB downloaded" -f ($tableBytes / 1MB))
                    }
                }
                elseif ($tableStatus -eq 'Queued' -or $tableStatus -eq 'Pending') {
                    Write-Progress -Id $tableProgressId -ParentId $parallelParentProgressId -Activity "$tableName.zip" -Status 'Queued' -PercentComplete 0
                }
                elseif ($tableStatus -eq 'Skipped') {
                    Write-Progress -Id $tableProgressId -ParentId $parallelParentProgressId -Activity "$tableName.zip" -Status 'Skipped (unchanged)' -PercentComplete 100
                }
                elseif ($tableStatus -eq 'Downloaded') {
                    Write-Progress -Id $tableProgressId -ParentId $parallelParentProgressId -Activity "$tableName.zip" -Status 'Downloaded' -PercentComplete 100
                }
                else {
                    Write-Progress -Id $tableProgressId -ParentId $parallelParentProgressId -Activity "$tableName.zip" -Status 'Failed' -PercentComplete 100
                }
            }

            if ($activeJobs.Count -gt 0) {
                Wait-Job -Job ($activeJobs | Select-Object -ExpandProperty Job) -Any -Timeout 1 | Out-Null
            }
        }

        Write-Progress -Id $parallelParentProgressId -Activity "Downloading FEC bulk data ($Cycle)" -Status "$($downloadResults.Count) / $($downloadPlans.Count) completed" -PercentComplete 100

        foreach ($result in $downloadResults) {
            if ($result.Status -eq 'Downloaded') {
                $downloadedCount++
                Write-Verbose "DOWNLOADED  $($result.Name).zip"
            }
            else {
                $failedCount++
                Write-Verbose "FAILED  $($result.Name).zip : $($result.Error)"
            }
        }

        if ($failedCount -gt 0) {
            throw "$failedCount download(s) failed. Re-run with -Verbose for details."
        }
    }

    Write-Host "Completed cycle ${Cycle}: downloaded $downloadedCount, skipped $skippedCount, failed $failedCount, total $totalFiles."
}
finally {
    Pop-Location
}