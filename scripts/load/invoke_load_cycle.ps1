<#
.SYNOPSIS
Runs DuckDB schema and transform SQL batches for an ETL cycle.
#>

[CmdletBinding()]
param(
    [int]$Cycle,

    [string]$DuckDbPath = "db/fec.duckdb",

    [string]$SchemaSqlDirectory = "sql/schema",

    [string]$TransformSqlDirectory = "sql/transform"
)

$modulePath = Join-Path -Path $PSScriptRoot -ChildPath "../modules/ETLModule.psd1"
Import-Module -Force $modulePath

Invoke-EtlCycleLoad -Cycle $Cycle -DuckDbPath $DuckDbPath -SchemaSqlDirectory $SchemaSqlDirectory -TransformSqlDirectory $TransformSqlDirectory
