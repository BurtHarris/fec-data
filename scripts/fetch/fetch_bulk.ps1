param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$programFilesX86 = [System.Environment]::GetEnvironmentVariable('ProgramFiles(x86)')

$gitBashCandidates = @(
    $env:ProgramFiles,
    $programFilesX86
) | Where-Object { $_ } | ForEach-Object {
    Join-Path $_ 'Git\bin\bash.exe'
} | Where-Object { Test-Path $_ }

$gitBash = $gitBashCandidates | Select-Object -First 1

if (-not $gitBash) {
    Write-Error 'Git Bash was not found. Install Git for Windows or rerun .\scripts\setup-tools.ps1.'
    exit 1
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$scriptPath = './scripts/fetch/fetch_bulk.sh'

Push-Location $repoRoot

try {
    & $gitBash $scriptPath @Arguments
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}