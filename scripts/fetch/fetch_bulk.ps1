param(
    [Parameter(Position = 0)]
    [string]$Cycle
)

$ErrorActionPreference = 'Stop'

if (-not $Cycle) {
    Write-Error 'Usage: .\scripts\fetch\fetch_bulk.ps1 <cycle>`n  e.g. .\scripts\fetch\fetch_bulk.ps1 2026'
    exit 1
}

if ($Cycle -notmatch '^\d{4}$') {
    Write-Error 'Cycle must be a four-digit election year, e.g. 2026.'
    exit 1
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
        [string]$Destination
    )

    Invoke-WebRequest -Uri $Url -OutFile $Destination -MaximumRedirection 10
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$yy = $Cycle.Substring(2)
$baseUrl = "https://www.fec.gov/files/bulk-downloads/$Cycle"
$rawDest = Join-Path $repoRoot "data\$Cycle\raw"
$byDateDest = Join-Path $rawDest 'by_date'

$files = @(
    "weball$yy",
    "indiv$yy",
    "oppexp$yy",
    "pas2$yy",
    "oth$yy",
    "cm$yy",
    "cn$yy"
)

$itcontFiles = @(
    "itcont_${Cycle}_20200101_20200131.txt",
    "itcont_${Cycle}_20200201_20200229.txt"
)

New-Item -ItemType Directory -Path $rawDest -Force | Out-Null
New-Item -ItemType Directory -Path $byDateDest -Force | Out-Null

Write-Host "Downloading FEC bulk data - cycle $Cycle"
Write-Host "Destination: $rawDest"
Write-Host ''

Push-Location $repoRoot

try {
    foreach ($name in $files) {
        $zipPath = Join-Path $rawDest "$name.zip"
        $url = "$baseUrl/$name.zip"
        $metaPath = Join-Path $rawDest ".$name.meta"

        $remoteSignature = Get-RemoteSignature -Url $url
        $previousSignature = ''

        if (Test-Path $metaPath) {
            $previousSignature = (Get-Content -Path $metaPath -Raw).Trim()
        }

        if ((Test-Path $zipPath) -and $previousSignature -and ($remoteSignature -eq $previousSignature)) {
            Write-Host "[SKIP]  $name.zip unchanged on server"
            Write-Host ''
            continue
        }

        Write-Host "[GET]   $name.zip"
        Save-File -Url $url -Destination $zipPath
        Set-Content -Path $metaPath -Value $remoteSignature
        Write-Host "[OK]    $name downloaded"
        Write-Host ''
    }

    foreach ($file in $itcontFiles) {
        $url = "$baseUrl/by_date/$file"
        $destinationFile = Join-Path $byDateDest $file

        if (Test-Path $destinationFile) {
            Write-Host "[SKIP] $file already exists"
            continue
        }

        Write-Host "[GET] $file"
        Save-File -Url $url -Destination $destinationFile
        Write-Host "[OK] $file downloaded"
        Write-Host ''
    }

    Write-Host "All incremental files ready in ${byDateDest}/"
    Get-ChildItem -Path $byDateDest | Select-Object Length, LastWriteTime, Name
}
finally {
    Pop-Location
}