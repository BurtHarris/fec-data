<#
.SYNOPSIS
Expands cycle-scoped bronze archive files into the silver layer.

.DESCRIPTION
Wrapper script that imports the shared ETL module and runs archive expansion
from data/{cycle}/bronze to data/{cycle}/silver.

By default, non-incremental expansion skips `indiv` `by_date` entries
to speed up baseline and test runs.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [int]$Cycle,

    [string]$SourceZone = "bronze",

    [string]$TargetZone = "silver",

    # Include full extraction (including indiv/by_date) when running incremental workflows.
    [switch]$Incremental,

    [string]$SevenZipPath = "C:\Program Files\7-Zip\7z.exe"
)

$modulePath = Join-Path -Path $PSScriptRoot -ChildPath "../modules/ETLModule.psd1"
Import-Module -Force $modulePath

Expand-EtlCycleArchives -Cycle $Cycle -SourceZone $SourceZone -TargetZone $TargetZone -Incremental:$Incremental -SevenZipPath $SevenZipPath