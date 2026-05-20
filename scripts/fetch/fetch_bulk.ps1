param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

. (Join-Path $PSScriptRoot '..\common\invoke_external_tool.ps1')

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
$session = New-LogSession -OperationName 'fetch_bulk'

Push-Location $repoRoot

try {
    Write-StructuredLog -Session $session -Level 'INFO' -Message 'Starting fetch bulk wrapper execution' -Tool 'bash' -Metadata @{
        arguments = $Arguments
        logFile   = $session.LogFile
    }

    $toolArguments = @($scriptPath) + $Arguments
    $result = Invoke-ExternalTool -ToolPath $gitBash -Arguments $toolArguments -Session $session -ToolName 'bash' -Activity 'Running fetch_bulk.sh' -ThrowOnError:$false
    if ($result.ExitCode -ne 0) {
        Write-StructuredLog -Session $session -Level 'ERROR' -Message "fetch_bulk.sh exited with code $($result.ExitCode)" -Tool 'bash'
        exit $result.ExitCode
    }

    Write-StructuredLog -Session $session -Level 'INFO' -Message 'fetch_bulk wrapper completed successfully' -Tool 'bash'
    exit 0
}
catch {
    Write-StructuredLog -Session $session -Level 'ERROR' -Message "Unexpected failure running fetch_bulk wrapper: $_" -Tool 'bash'
    exit 1
}
finally {
    Pop-Location
}
