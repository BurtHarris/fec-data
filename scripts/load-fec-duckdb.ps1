[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{4}$')]
    [string]$Cycle,
    [Parameter(Position = 1)]
    [string[]]$Tables,
    [string]$DbPath = 'db/fec.duckdb',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $repoRoot

try {
    $uvCommand = New-Object 'System.Collections.Generic.List[string]'
    [void]$uvCommand.Add('run')
    [void]$uvCommand.Add('load')
    [void]$uvCommand.Add('--cycle')
    [void]$uvCommand.Add($Cycle)
    [void]$uvCommand.Add('--db-path')
    [void]$uvCommand.Add($DbPath)

    if ($Force) {
        [void]$uvCommand.Add('--force')
    }

    if ($Tables -and $Tables.Count -gt 0) {
        $normalizedTables = @(
            $Tables |
                ForEach-Object { $_ -split ',' } |
                ForEach-Object { $_.Trim().ToLowerInvariant() } |
                Where-Object { $_ -ne '' }
        )

        if ($normalizedTables.Count -gt 0) {
            [void]$uvCommand.Add('--tables')
            foreach ($table in $normalizedTables) {
                [void]$uvCommand.Add($table)
            }
        }
    }

    Write-Host "Delegating load to Python CLI: uv $($uvCommand -join ' ')"
    & uv @($uvCommand.ToArray())
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
