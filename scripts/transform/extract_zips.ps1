<#
.SYNOPSIS
Expands cycle-scoped raw archive files into the staging layer.

.DESCRIPTION
Wrapper script that imports the shared ETL module and runs archive expansion
from data/{cycle}/raw to data/{cycle}/staging.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [int]$Cycle,

    [string]$SourceZone = "raw",

    [string]$TargetZone = "staging",

    [string]$SevenZipPath = "C:\Program Files\7-Zip\7z.exe"
)

$modulePath = Join-Path -Path $PSScriptRoot -ChildPath "../modules/ETLModule.psd1"
Import-Module -Force $modulePath

Expand-EtlCycleArchives -Cycle $Cycle -SourceZone $SourceZone -TargetZone $TargetZone -SevenZipPath $SevenZipPath