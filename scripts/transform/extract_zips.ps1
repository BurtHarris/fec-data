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

# Derive the directory path from the cycle
$Directory = Join-Path -Path "data/raw" -ChildPath $Cycle

# Ensure the directory exists
if (-Not (Test-Path -Path $Directory -PathType Container)) {
    Write-Error "Error: Directory $Directory does not exist."
    exit 1
}

# Extract and process each ZIP file in the directory
Get-ChildItem -Path $Directory -Filter "*.zip" | ForEach-Object {
    $zipFile = $_
    Write-Host "[UNZIP] Extracting $($zipFile.Name)"

    # Extract ZIP contents to the same directory
    try {
        [System.IO.Compression.ZipFile]::ExtractToDirectory($zipFile.FullName, $Directory)
    } catch {
        Write-Error "Failed to extract $($zipFile.Name): $_"
        return
    }

    # Determine the staging directory path
    $stagingDir = Join-Path -Path "data/staging" -ChildPath $Cycle

    # Ensure the staging directory exists
    if (-Not (Test-Path -Path $stagingDir)) {
        New-Item -ItemType Directory -Path $stagingDir | Out-Null
    }

    Write-Host "[MOVE] Moving extracted files to $stagingDir"
    # Move all extracted files to the staging directory, excluding .meta files
    Get-ChildItem -Path $Directory -File | Where-Object { $_.Extension -ne ".zip" -and $_.Extension -ne ".meta" } | ForEach-Object {
        Move-Item -Path $_.FullName -Destination $stagingDir -Force
    }

    Write-Host "[CLEANUP] Cleaning up extracted files from $($zipFile.Name)"
    # Clean up extracted files from the raw directory, excluding .meta files
    Get-ChildItem -Path $Directory -File | Where-Object { $_.Extension -ne ".zip" -and $_.Extension -ne ".meta" } | Remove-Item -Force
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