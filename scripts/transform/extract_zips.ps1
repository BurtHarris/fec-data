<#
.SYNOPSIS
Expands cycle-scoped bronze archive files into the silver layer.

.DESCRIPTION
Wrapper script that imports the shared ETL module and runs archive expansion
from data/{cycle}/bronze to data/{cycle}/silver.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [int]$Cycle,

    [string]$SourceZone = "bronze",

    [string]$TargetZone = "silver",

    [string]$SevenZipPath = "C:\Program Files\7-Zip\7z.exe"
)

$modulePath = Join-Path -Path $PSScriptRoot -ChildPath "../modules/ETLModule.psd1"
Import-Module -Force $modulePath

Expand-EtlCycleArchives -Cycle $Cycle -SourceZone $SourceZone -TargetZone $TargetZone -SevenZipPath $SevenZipPath