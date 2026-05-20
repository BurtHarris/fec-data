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

. (Join-Path $PSScriptRoot '..\common\invoke_external_tool.ps1')

$7zipPath = "C:\Program Files\7-Zip\7z.exe"  # Adjust path if 7-Zip is installed elsewhere
$session = New-LogSession -OperationName "extract_zips_$Cycle"
Write-StructuredLog -Session $session -Level 'INFO' -Message "Starting ZIP extraction for cycle $Cycle" -Tool '7zip' -Metadata @{
    cycle   = $Cycle
    logFile = $session.LogFile
}

# Derive the directory path from the cycle
$Directory = Join-Path -Path "data" -ChildPath (Join-Path $Cycle "raw")

# Ensure the directory exists
if (-Not (Test-Path -Path $Directory -PathType Container)) {
    Write-StructuredLog -Session $session -Level 'ERROR' -Message "Directory does not exist: $Directory"
    exit 1
}

# Derive the staging directory path
$stagingDir = Join-Path -Path "data" -ChildPath (Join-Path $Cycle "staging")

# Ensure the staging directory exists
if (-Not (Test-Path -Path $stagingDir)) {
    New-Item -ItemType Directory -Path $stagingDir | Out-Null
}

# Extract all ZIP files in the directory at once using 7-Zip with multi-threading
if (-Not (Test-Path -Path $7zipPath)) {
    Write-StructuredLog -Session $session -Level 'ERROR' -Message "7-Zip executable not found at $7zipPath. Please ensure 7-Zip is installed." -Tool '7zip'
    exit 1
}

# 7-Zip requires the output directory flag and path in one argument ("-o<path>").
$zipFiles = Get-ChildItem -Path $Directory -Filter '*.zip' -File
if ($zipFiles.Count -eq 0) {
    Write-StructuredLog -Session $session -Level 'ERROR' -Message "No ZIP files found in $Directory." -Tool '7zip'
    exit 1
}
else {
    $zipFilePaths = $zipFiles | ForEach-Object { $_.FullName }
    $arguments = @('x') + $zipFilePaths + @("-o$stagingDir", '-y', '-mmt')
    try {
        Write-StructuredLog -Session $session -Level 'INFO' -Message "Extracting $($zipFiles.Count) ZIP file(s) in $Directory using multi-threading" -Tool '7zip'
        [void](Invoke-7Zip -SevenZipPath $7zipPath -Arguments $arguments -Session $session)
    }
    catch {
        Write-StructuredLog -Session $session -Level 'ERROR' -Message "Failed to extract ZIP files: $_" -Tool '7zip'
        exit 1
    }
}

# Cross-check .meta files against ZIP files
Write-StructuredLog -Session $session -Level 'INFO' -Message 'Verifying .meta files against ZIP files'
Get-ChildItem -Path $Directory -Filter "*.meta" | ForEach-Object {
    $metaFile = $_
    # Assumes .meta and .zip filenames share the same base name.
    $zipFileName = [System.IO.Path]::ChangeExtension($metaFile.Name, '.zip')
    $zipFile = Join-Path -Path $Directory -ChildPath $zipFileName
    Write-StructuredLog -Session $session -Level 'INFO' -Message "Meta file: $($metaFile.FullName)"
    Write-StructuredLog -Session $session -Level 'INFO' -Message "Expected ZIP file: $zipFile"
    if (Test-Path $zipFile) {
        Write-StructuredLog -Session $session -Level 'INFO' -Message "ZIP file found: $zipFile"
    } else {
        Write-StructuredLog -Session $session -Level 'WARN' -Message "ZIP file missing: $zipFile"
    }
}

Write-StructuredLog -Session $session -Level 'INFO' -Message "All ZIP files for cycle $Cycle have been processed and extracted files moved to the staging directory."
