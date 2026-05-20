<#
.SYNOPSIS
Downloads and refreshes cycle-scoped bronze archives used by ETL.

.DESCRIPTION
Lightweight wrapper that imports the shared ETL module and invokes
the cycle bronze sync command.

.PARAMETER Cycle
Election cycle year (for example: 2024).

.PARAMETER Files
Archive file prefixes to fetch.

.PARAMETER Force
Bypass conditional cache checks.

.PARAMETER LandingZone
Data landing folder under cycle. Default is bronze.
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

    [string]$LandingZone = "bronze",

    [switch]$Force,

    [switch]$Sequential
)

$modulePath = Join-Path -Path $PSScriptRoot -ChildPath "../modules/ETLModule.psd1"
Import-Module -Force $modulePath

Invoke-FecCycleRawSync -Cycle $Cycle -FilePrefixes $Files -LandingZone $LandingZone -Force:$Force -Sequential:$Sequential
