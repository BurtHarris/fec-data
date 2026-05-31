# setup-tools.ps1
# Provisions or updates required tools via winget configure.
# Safe to rerun — winget configure is idempotent and will upgrade packages
# to the configured version if they are already installed.
#
# Installs current local ETL dependencies:
# - Python 3.11
# - uv
# - DuckDB CLI
# - Git
# - jq
# - 7-Zip
# - ripgrep
# - GitHub CLI
# - fd
# - fzf
# - bat
# - delta
#
# Also pins the user shell to the provisioned Python 3.11 runtime so
# `python` and `py` resolve consistently even when WindowsApps shims or
# newer side-by-side Python installs are present.
#
# This script is run manually by choice; it is never called automatically
# by the ETL pipeline.
# If you or an agent needs to change installed tools, update
# .config/configuration.winget first instead of adding direct installs here.
#
# Run from the project root:
#   ./scripts/setup-tools.ps1

$ErrorActionPreference = 'Stop'

function Normalize-PathEntry {
    param(
        [AllowNull()]
        [AllowEmptyString()]
        [string]$PathEntry
    )

    if ([string]::IsNullOrWhiteSpace($PathEntry)) {
        return $null
    }

    return $PathEntry.Trim().TrimEnd('\')
}

function Get-Python311InstallDir {
    $pythonRoot = Join-Path $env:LocalAppData 'Programs\Python'
    $installDir = Get-ChildItem -Path $pythonRoot -Directory -Filter 'Python311*' |
        Sort-Object FullName |
        Select-Object -First 1

    if ($null -eq $installDir) {
        throw "Python 3.11 install directory not found under $pythonRoot."
    }

    return $installDir.FullName
}

function Set-PreferredUserPathEntries {
    param(
        [string[]]$PreferredEntries
    )

    $normalizedPreferredEntries = foreach ($entry in $PreferredEntries) {
        $normalizedEntry = Normalize-PathEntry -PathEntry $entry
        if ($null -ne $normalizedEntry) {
            $normalizedEntry
        }
    }

    $currentUserPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $currentEntries = @()
    if (-not [string]::IsNullOrWhiteSpace($currentUserPath)) {
        $currentEntries = $currentUserPath -split ';'
    }

    $remainingEntries = foreach ($entry in $currentEntries) {
        $normalizedEntry = Normalize-PathEntry -PathEntry $entry
        if (($null -ne $normalizedEntry) -and ($normalizedPreferredEntries -notcontains $normalizedEntry)) {
            $normalizedEntry
        }
    }

    $updatedUserPath = (($normalizedPreferredEntries + $remainingEntries) | Select-Object -Unique) -join ';'
    [Environment]::SetEnvironmentVariable('Path', $updatedUserPath, 'User')

    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    if ([string]::IsNullOrWhiteSpace($machinePath)) {
        $env:Path = $updatedUserPath
    }
    else {
        $env:Path = "$updatedUserPath;$machinePath"
    }
}

winget configure -f .config/configuration.winget --accept-configuration-agreements

$pythonInstallDir = Get-Python311InstallDir
$pythonLauncherDir = Join-Path $env:LocalAppData 'Programs\Python\Launcher'

if (-not (Test-Path $pythonLauncherDir)) {
    throw "Python launcher directory not found at $pythonLauncherDir."
}

Set-PreferredUserPathEntries -PreferredEntries @(
    $pythonInstallDir,
    (Join-Path $pythonInstallDir 'Scripts'),
    $pythonLauncherDir
)

[Environment]::SetEnvironmentVariable('PY_PYTHON', '3.11', 'User')
$env:PY_PYTHON = '3.11'

Write-Host "Pinned Python launcher to 3.11 and refreshed PATH for this session."
python --version
py --version
