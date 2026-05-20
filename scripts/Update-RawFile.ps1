<#
.SYNOPSIS
Updates cycle-scoped raw archives for the ETL pipeline.

.DESCRIPTION
Imports the local ETL module and runs cycle-based raw archive sync.
Directory layout remains year-first: data/{cycle}/raw.

.PARAMETER Cycle
The election cycle year (for example: 2024).

.PARAMETER Files
Archive file prefixes to download (for example: weball, indiv).

.PARAMETER Force
Forces download without conditional cache checks.

.PARAMETER Sequential
Reserved for future parallelization control; current implementation runs in order for easier debugging.

.PARAMETER LandingZone
Data landing folder under cycle. Default is raw.

.EXAMPLE
.\scripts\Update-RawFile.ps1 -Cycle 2024
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

    [string]$LandingZone = "raw",

    [switch]$Force,

    [switch]$Sequential
)

$modulePath = Join-Path -Path $PSScriptRoot -ChildPath "modules/ETLModule.psd1"
Import-Module -Force $modulePath

Invoke-FecCycleRawSync -Cycle $Cycle -FilePrefixes $Files -LandingZone $LandingZone -Force:$Force -Sequential:$Sequential
