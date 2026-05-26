<#
.SYNOPSIS
Extracts all ZIP files for a cycle into data/staging/<cycle>.

.DESCRIPTION
This script processes ZIP files in data/<cycle>/raw, extracts them into
data/<cycle>/staging, and retains the original ZIP files as the source cache.

.PARAMETER Cycle
The election cycle year (for example, 2020) to process ZIP files for.

.EXAMPLE
.\scripts\extract-zips.ps1 -Cycle 2020
#>

param (
    [Parameter(Mandatory = $true)]
    [int]$Cycle
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$rawDirectory = Join-Path $repoRoot "data\$Cycle\raw"
$stagingDirectory = Join-Path $repoRoot "data\$Cycle\staging"
$sevenZipPath = 'C:\Program Files\7-Zip\7z.exe'

if (-not (Test-Path -Path $rawDirectory -PathType Container)) {
    Write-Error "Directory not found: $rawDirectory"
    exit 1
}

if (-not (Test-Path -Path $sevenZipPath -PathType Leaf)) {
    Write-Error "7-Zip executable not found at $sevenZipPath."
    exit 1
}

New-Item -ItemType Directory -Path $stagingDirectory -Force | Out-Null

$zipFiles = Join-Path $rawDirectory '*.zip'
$arguments = "x `"$zipFiles`" -o`"$stagingDirectory`" -y -mmt"

try {
    Write-Host "[UNZIP] Extracting ZIP files from $rawDirectory"
    Start-Process -FilePath $sevenZipPath -ArgumentList $arguments -NoNewWindow -Wait -ErrorAction Stop
}
catch {
    Write-Error "Failed to extract ZIP files: $_"
    exit 1
}

Write-Host '[CHECK] Verifying .meta files against ZIP files'
Get-ChildItem -Path $rawDirectory -Filter '*.meta' | ForEach-Object {
    $metaFile = $_
    $expectedZipPath = Join-Path $rawDirectory (($metaFile.BaseName -replace '^\.', '') + '.zip')

    Write-Host "Meta File: $($metaFile.FullName)"
    Write-Host "Expected ZIP File: $expectedZipPath"

    if (Test-Path $expectedZipPath) {
        Write-Host "ZIP File Found: $expectedZipPath"
    }
    else {
        Write-Host "ZIP File Missing: $expectedZipPath"
    }
}

Write-Host "All ZIP files for cycle $Cycle were extracted to $stagingDirectory"