[CmdletBinding()]
param(
    [Parameter(Position = 0, HelpMessage = 'Election cycle year (e.g. 2026)')]
    [string]$Cycle = '2026',
    [Parameter(Position = 1, HelpMessage = 'Table names without cycle suffix (e.g. indiv, weball).')]
    [string[]]$Tables,
    [Parameter(HelpMessage = 'Force download even when local file and signature match.')]
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$defaultTables = @(
    'weball',
    'indiv',
    'oppexp',
    'pas2',
    'oth',
    'cm',
    'cn'
)

if (-not $Cycle) {
    Write-Error 'Usage: .\scripts\fetch-bulk.ps1 <cycle> [table1 table2 ...] [-Force]`n  e.g. .\scripts\fetch-bulk.ps1 2026 indiv weball -Force'
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
Write-Host ''

$progressId = 1
$totalFiles = $files.Count
$currentFile = 0
$downloadedCount = 0
$skippedCount = 0
$failedCount = 0

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

            Write-Progress -Id $progressId -Activity "Downloading FEC bulk data ($Cycle)" -Status "Checking $name.zip ($currentFile/$totalFiles)" -PercentComplete ([int](($currentFile - 1) * 100 / $totalFiles))

            $remoteSignature = Get-RemoteSignature -Url $url
            $previousSignature = ''

            if (Test-Path $metaPath) {
                $previousSignature = (Get-Content -Path $metaPath -Raw).Trim()
            }

            if ((-not $Force) -and (Test-Path $zipPath) -and $previousSignature -and ($remoteSignature -eq $previousSignature)) {
                Write-Progress -Id $progressId -Activity "Downloading FEC bulk data ($Cycle)" -Status "Skipped $name.zip (unchanged)" -PercentComplete ([int]($currentFile * 100 / $totalFiles))
                Write-Verbose "SKIPPED  $name.zip"
                $skippedCount++
                continue
            }

            Write-Progress -Id $progressId -Activity "Downloading FEC bulk data ($Cycle)" -Status "GET $name.zip" -PercentComplete ([int](($currentFile - 1) * 100 / $totalFiles))
            Save-File -Url $url -Destination $zipPath -ProgressId 2 -Activity "Downloading $name.zip"
            Set-Content -Path $metaPath -Value $remoteSignature
            $downloadedCount++
            Write-Verbose "DOWNLOADED  $name.zip"
            Write-Progress -Id $progressId -Activity "Downloading FEC bulk data ($Cycle)" -Status "OK $name.zip downloaded" -PercentComplete ([int]($currentFile * 100 / $totalFiles))
        }
        catch {
            $failedCount++
            Write-Verbose "FAILED  $name.zip"
            throw
        }
    }

    Write-Progress -Id $progressId -Activity "Downloading FEC bulk data ($Cycle)" -Completed
    Write-Host "Completed cycle ${Cycle}: downloaded $downloadedCount, skipped $skippedCount, failed $failedCount, total $totalFiles."
}
finally {
    Pop-Location
}