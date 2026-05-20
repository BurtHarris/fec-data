<#
.SYNOPSIS
Extracts all ZIP files in a given directory and moves processed files to `data/staging/<cycle>`.
Retains ZIP files as a cache and cleans up extracted files after processing.

.DESCRIPTION
This script processes ZIP files in a specified directory. It extracts the contents of each ZIP file,
moves the extracted files to a `data/staging/<cycle>` directory, and retains the original ZIP files
for caching purposes. Extracted files are cleaned up from the raw directory after processing.

.PARAMETER Cycle
The election cycle year (e.g., 2020) to process ZIP files for.

.EXAMPLE
.\extract_zips.ps1 -Cycle 2020
#>

param (
    [Parameter(Mandatory = $true)]
    [int]$Cycle
)

$7zipPath = "C:\Program Files\7-Zip\7z.exe"  # Adjust path if 7-Zip is installed elsewhere

# Derive the directory path from the cycle
$Directory = Join-Path -Path "data/raw" -ChildPath $Cycle

# Ensure the directory exists
if (-Not (Test-Path -Path $Directory -PathType Container)) {
    Write-Error "Error: Directory $Directory does not exist."
    exit 1
}

# Derive the staging directory path
$stagingDir = Join-Path -Path "data/staging" -ChildPath $Cycle

# Ensure the staging directory exists
if (-Not (Test-Path -Path $stagingDir)) {
    New-Item -ItemType Directory -Path $stagingDir | Out-Null
}

# Extract all ZIP files in the directory at once using 7-Zip with multi-threading
$7zipPath = "C:\Program Files\7-Zip\7z.exe"  # Adjust path if 7-Zip is installed elsewhere
if (-Not (Test-Path -Path $7zipPath)) {
    Write-Error "7-Zip executable not found at $7zipPath. Please ensure 7-Zip is installed."
    exit 1
}

# Use wildcard to process all ZIP files in the directory
$zipFiles = Join-Path -Path $Directory -ChildPath "*.zip"

$arguments = "x `"$zipFiles`" -o`"$stagingDir`" -y -mmt"
try {
    Write-Host "[UNZIP] Extracting all ZIP files in $Directory using multi-threading"
    Start-Process -FilePath $7zipPath -ArgumentList $arguments -NoNewWindow -Wait -ErrorAction Stop
} catch {
    Write-Error "Failed to extract ZIP files: $_"
    exit 1
}

# Cross-check .meta files against ZIP files
Write-Host "[CHECK] Verifying .meta files against ZIP files"
Get-ChildItem -Path $Directory -Filter "*.meta" | ForEach-Object {
    $metaFile = $_
    $zipFile = $metaFile.FullName -replace '^.*\\\\([^.]+)\\\.meta$', "$Directory/$1.zip"
    Write-Host "Meta File: $($metaFile.FullName)"
    Write-Host "Expected ZIP File: $zipFile"
    if (Test-Path $zipFile) {
        Write-Host "ZIP File Found: $zipFile"
    } else {
        Write-Host "ZIP File Missing: $zipFile"
    }
}

Write-Host "All ZIP files for cycle $Cycle have been processed and extracted files moved to the staging directory."