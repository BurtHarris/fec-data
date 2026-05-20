Set-StrictMode -Version Latest

function Sync-EtlArchiveSet {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [int]$Cycle,

        [Parameter(Mandatory = $true)]
        [string]$BaseUrl,

        [Parameter(Mandatory = $true)]
        [string[]]$ArchiveNames,

        [string]$LandingZone = "bronze",

        [string]$DataRoot = "data",

        [string]$MetadataFileName = "metadata_log.csv",

        [switch]$Force,

        [switch]$Sequential
    )

    $destination = Join-Path -Path $DataRoot -ChildPath "$Cycle/$LandingZone"
    $metadataPath = Join-Path -Path $destination -ChildPath $MetadataFileName

    New-Item -ItemType Directory -Force -Path $destination | Out-Null

    if (-not (Test-Path -Path $metadataPath)) {
        "Timestamp,FileName,ETag,LastModified,ContentLength,Url" | Out-File -FilePath $metadataPath -Encoding utf8
    }

    Write-Host "Syncing archive files for cycle $Cycle"
    Write-Host "Destination: $destination"

    foreach ($name in $ArchiveNames) {
        $zipName = "$name.zip"
        $url = "$BaseUrl/$zipName"
        $zipPath = Join-Path -Path $destination -ChildPath $zipName

        $curlArgs = @("-L", "-o", $zipPath)
        if (-not $Force) {
            $curlArgs += @("-z", $zipPath)
        }
        $curlArgs += $url

        Write-Host "Downloading $zipName"
        $process = Start-Process -FilePath "curl.exe" -ArgumentList $curlArgs -NoNewWindow -PassThru -Wait
        if ($process.ExitCode -ne 0) {
            throw "Failed to download $zipName from $url"
        }

        $headers = & curl.exe -sSLI $url
        if (-not $headers) {
            Write-Warning "Skipping metadata for $zipName because no response headers were returned."
            continue
        }

        $etag = ($headers | Select-String -Pattern "(?i)^etag:" | Select-Object -Last 1).Line
        $lastModified = ($headers | Select-String -Pattern "(?i)^last-modified:" | Select-Object -Last 1).Line
        $contentLength = ($headers | Select-String -Pattern "(?i)^content-length:" | Select-Object -Last 1).Line

        $etagValue = if ($etag) { ($etag -split ":", 2)[1].Trim().Trim('"') } else { "" }
        $lastModifiedValue = if ($lastModified) { ($lastModified -split ":", 2)[1].Trim() } else { "" }
        $contentLengthValue = if ($contentLength) { ($contentLength -split ":", 2)[1].Trim() } else { "" }

        $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        $metadataLine = "$timestamp,$zipName,$etagValue,$lastModifiedValue,$contentLengthValue,$url"
        Add-Content -Path $metadataPath -Value $metadataLine
    }

    Get-ChildItem -Path $destination -File | Format-Table Name, Length
}

function Invoke-FecCycleRawSync {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [ValidateScript({
            if ($_ -gt 2000 -and ($_ % 2 -eq 0)) {
                $true
            } else {
                throw 'Cycle must be an even number greater than 2000.'
            }
        })]
        [int]$Cycle,

        [string[]]$FilePrefixes = @("weball", "indiv", "oppexp", "pas2", "oth", "cm", "cn"),

        [string]$LandingZone = "bronze",

        [switch]$Force,

        [switch]$Sequential
    )

    $yy = $Cycle.ToString().Substring(2)
    $archiveNames = $FilePrefixes | ForEach-Object { "$_$yy" }
    $baseUrl = "https://www.fec.gov/files/bulk-downloads/$Cycle"

    Sync-EtlArchiveSet -Cycle $Cycle -BaseUrl $baseUrl -ArchiveNames $archiveNames -LandingZone $LandingZone -Force:$Force -Sequential:$Sequential
}

function Expand-EtlCycleArchives {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [int]$Cycle,

        [string]$SourceZone = "bronze",

        [string]$TargetZone = "silver",

        [string]$DataRoot = "data",

        [string]$SevenZipPath = "C:\Program Files\7-Zip\7z.exe"
    )

    $sourceDir = Join-Path -Path $DataRoot -ChildPath "$Cycle/$SourceZone"
    $targetDir = Join-Path -Path $DataRoot -ChildPath "$Cycle/$TargetZone"

    if (-not (Test-Path -Path $sourceDir -PathType Container)) {
        throw "Source directory not found: $sourceDir"
    }

    if (-not (Test-Path -Path $SevenZipPath -PathType Leaf)) {
        throw "7-Zip executable not found at $SevenZipPath"
    }

    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

    $zipFiles = Get-ChildItem -Path $sourceDir -Filter "*.zip" -File
    if (-not $zipFiles) {
        Write-Warning "No zip files found in $sourceDir"
        return
    }

    foreach ($zipFile in $zipFiles) {
        Write-Host "Extracting $($zipFile.Name) -> $targetDir"
        $arguments = @("x", $zipFile.FullName, "-o$targetDir", "-y", "-mmt")
        $process = Start-Process -FilePath $SevenZipPath -ArgumentList $arguments -NoNewWindow -PassThru -Wait
        if ($process.ExitCode -ne 0) {
            throw "Failed to extract $($zipFile.FullName)"
        }
    }
}

function Invoke-DuckDbSqlBatch {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$DuckDbPath,

        [Parameter(Mandatory = $true)]
        [string]$SqlDirectory,

        [string]$StepName = "sql-batch"
    )

    if (-not (Test-Path -Path $SqlDirectory -PathType Container)) {
        Write-Warning "Skipping ${StepName}: directory not found ($SqlDirectory)"
        return
    }

    $sqlFiles = Get-ChildItem -Path $SqlDirectory -Filter "*.sql" -File | Sort-Object Name
    if (-not $sqlFiles) {
        Write-Warning "Skipping ${StepName}: no SQL files found in $SqlDirectory"
        return
    }

    $repoRoot = (Resolve-Path (Join-Path -Path $PSScriptRoot -ChildPath "../..")).Path
    Push-Location $repoRoot
    try {
        foreach ($sqlFile in $sqlFiles) {
            Write-Host "Running $StepName file: $($sqlFile.Name)"
            $sqlPath = $sqlFile.FullName.Replace('\\', '/')
            & duckdb $DuckDbPath -c ".read '$sqlPath'"
            if ($LASTEXITCODE -ne 0) {
                throw "DuckDB failed while running $($sqlFile.FullName)"
            }
        }
    } finally {
        Pop-Location
    }
}

function Invoke-EtlCycleLoad {
    [CmdletBinding()]
    param(
        [int]$Cycle,

        [string]$DuckDbPath = "db/fec.duckdb",

        [string]$SchemaSqlDirectory = "sql/schema",

        [string]$TransformSqlDirectory = "sql/transform"
    )

    if ($Cycle) {
        Write-Host "Starting load for cycle $Cycle"
    }

    Invoke-DuckDbSqlBatch -DuckDbPath $DuckDbPath -SqlDirectory $SchemaSqlDirectory -StepName "schema"
    Invoke-DuckDbSqlBatch -DuckDbPath $DuckDbPath -SqlDirectory $TransformSqlDirectory -StepName "transform"
}

Export-ModuleMember -Function Sync-EtlArchiveSet, Invoke-FecCycleRawSync, Expand-EtlCycleArchives, Invoke-EtlCycleLoad