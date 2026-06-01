[CmdletBinding()]
param(
    [Parameter(Position = 0, Mandatory = $true)]
    [ValidateSet('fetch', 'load')]
    [string]$Command,

    # Shared
    [string]$CoverageConfig = 'config\data_scope.yml',
    [switch]$NoSync,

    # fetch
    [int[]]$Cycles,
    [string[]]$Tables,
    [switch]$Force,
    [int]$Parallelism = 4,
    [double]$ProgressInterval = 5.0,
    [switch]$StrictCoverage,

    # load
    [int]$Cycle,
    [int]$DbtThreads = 1,
    [string[]]$LoadTables,
    [string]$Select,
    [string]$ProfilesDir = '.'
)

$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Resolve-ConfiguredCycle([string]$repoRoot, [string]$coverageConfig) {
    $cfgPathLiteral = $coverageConfig.Replace('"', '\"')

    $code = @"
from pathlib import Path
from pipeline.etl_config import repo_root
from pipeline.data_scope import load_data_scope_config, parse_year_range

root = repo_root()
cfg_path = Path(r\"$cfgPathLiteral\")
if not cfg_path.is_absolute():
    cfg_path = root / cfg_path
cfg = load_data_scope_config(cfg_path)
start, end = parse_year_range(cfg.get(\"facts\"), \"facts\")
cycle = end if end % 2 == 0 else end - 1
if cycle < start:
    cycle = start if start % 2 == 0 else start + 1
print(cycle)
"@

    $resolved = (& uv run python -c $code).Trim()
    if (-not $resolved) {
        throw "Could not resolve a default cycle from $coverageConfig"
    }
    return [int]$resolved
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv not found on PATH. Install uv, then run 'uv sync' from repo root."
}

if (-not $NoSync) {
    & uv sync | Out-Host
}

if ($Command -eq 'fetch') {
    $args = @('run', 'download', '--coverage-config', $CoverageConfig, '--parallelism', $Parallelism, '--progress-interval', $ProgressInterval)
    if ($Cycles) { $args += @('--cycles') + $Cycles }
    if ($Tables) { $args += @('--tables') + $Tables }
    if ($StrictCoverage) { $args += '--strict-coverage' }
    if ($Force) { $args += '--force' }

    & uv @args
    exit $LASTEXITCODE
}

if ($Command -eq 'load') {
    if (-not $Cycle) {
        $Cycle = Resolve-ConfiguredCycle -repoRoot $repoRoot -coverageConfig $CoverageConfig
    }

    $args = @('run', 'load', '--cycle', $Cycle, '--dbt-threads', $DbtThreads, '--profiles-dir', $ProfilesDir)
    if ($LoadTables) { $args += @('--tables') + $LoadTables }
    if ($Select) { $args += @('--select', $Select) }

    & uv @args
    exit $LASTEXITCODE
}

throw "Unknown command: $Command"