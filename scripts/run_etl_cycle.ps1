<#
.SYNOPSIS
Runs retrieve, transform, and load steps for a cycle-scoped ETL flow.

.DESCRIPTION
Defaults to running all steps. Use switches to run targeted phases.
#>

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

    [string[]]$Files = @("weball", "indiv", "oppexp", "pas2", "oth", "cm", "cn"),

    [switch]$Retrieve,

    [switch]$Transform,

    [switch]$Load,

    [switch]$Force,

    [string]$LandingZone = "raw",

    [string]$SourceZone = "raw",

    [string]$TargetZone = "staging",

    [string]$DuckDbPath = "db/fec.duckdb"
)

$runAll = (-not $Retrieve -and -not $Transform -and -not $Load)

if ($runAll -or $Retrieve) {
    Write-Host "[ETL] Retrieve step"
    & "$PSScriptRoot/Update-RawFile.ps1" -Cycle $Cycle -Files $Files -LandingZone $LandingZone -Force:$Force
    if ($LASTEXITCODE -ne 0) {
        throw "Retrieve step failed."
    }
}

if ($runAll -or $Transform) {
    Write-Host "[ETL] Transform step"
    & "$PSScriptRoot/transform/extract_zips.ps1" -Cycle $Cycle -SourceZone $SourceZone -TargetZone $TargetZone
    if ($LASTEXITCODE -ne 0) {
        throw "Transform step failed."
    }
}

if ($runAll -or $Load) {
    Write-Host "[ETL] Load step"
    & "$PSScriptRoot/load/invoke_load_cycle.ps1" -Cycle $Cycle -DuckDbPath $DuckDbPath
    if ($LASTEXITCODE -ne 0) {
        throw "Load step failed."
    }
}

Write-Host "[ETL] Completed cycle $Cycle"
