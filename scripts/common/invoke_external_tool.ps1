Set-StrictMode -Version Latest

function New-LogSession {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$OperationName
    )

    $repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
    $logsDir = Join-Path $repoRoot 'logs'

    if (-not (Test-Path -LiteralPath $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir | Out-Null
    }

    $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $sessionId = '{0}-{1}-{2}' -f $OperationName, $timestamp, ([Guid]::NewGuid().ToString('N'))
    $logFile = Join-Path $logsDir "$sessionId.jsonl"

    New-Item -ItemType File -Path $logFile -Force | Out-Null

    return [PSCustomObject]@{
        SessionId = $sessionId
        LogFile   = $logFile
    }
}

function Write-StructuredLog {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [pscustomobject]$Session,

        [Parameter(Mandatory = $true)]
        [ValidateSet('INFO', 'WARN', 'ERROR')]
        [string]$Level,

        [Parameter(Mandatory = $true)]
        [string]$Message,

        [string]$Tool,

        [hashtable]$Metadata
    )

    $entry = [ordered]@{
        timestamp = (Get-Date).ToString('o')
        sessionId = $Session.SessionId
        level     = $Level
        message   = $Message
    }

    if ($Tool) {
        $entry.tool = $Tool
    }

    if ($Metadata) {
        foreach ($key in $Metadata.Keys) {
            $entry[$key] = $Metadata[$key]
        }
    }

    $line = ($entry | ConvertTo-Json -Compress -Depth 10)
    Add-Content -Path $Session.LogFile -Value $line

    $consoleMessage = '[{0}] [{1}] {2}' -f $entry.timestamp, $entry.level, $Message
    switch ($Level) {
        'ERROR' { Write-Host $consoleMessage -ForegroundColor Red }
        'WARN' { Write-Host $consoleMessage -ForegroundColor Yellow }
        default { Write-Host $consoleMessage -ForegroundColor Cyan }
    }
}

function ConvertTo-ProcessArguments {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    # Fallback for hosts that do not expose ProcessStartInfo.ArgumentList (for example, Windows PowerShell on .NET Framework).
    # This is intentionally minimal and only used in that compatibility path for simple argument values.
    return ($Arguments | ForEach-Object {
            if ($_ -match '[\s"]') {
                '"' + ($_ -replace '"', '""') + '"'
            }
            else {
                $_
            }
        }) -join ' '
}

function Invoke-ExternalTool {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$ToolPath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [pscustomobject]$Session,

        [Parameter(Mandatory = $true)]
        [string]$ToolName,

        [string]$Activity = 'Running external tool',

        [switch]$ThrowOnError = $true
    )

    $resolvedToolPath = $ToolPath
    if (-not (Test-Path -LiteralPath $ToolPath)) {
        $command = Get-Command $ToolPath -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            $resolvedToolPath = $command.Source
        }
    }

    if (-not (Test-Path -LiteralPath $resolvedToolPath)) {
        $msg = "Tool not found: $ToolPath"
        Write-StructuredLog -Session $Session -Level 'ERROR' -Message $msg -Tool $ToolName
        throw $msg
    }

    Write-StructuredLog -Session $Session -Level 'INFO' -Message "Starting $ToolName" -Tool $ToolName -Metadata @{
        command = $resolvedToolPath
        args    = $Arguments
    }

    Write-Progress -Activity $Activity -Status "Running $ToolName" -PercentComplete 10
    $startTime = Get-Date

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $resolvedToolPath
    # ArgumentList is available on newer runtimes and avoids manual escaping; use it when present.
    if ($startInfo.PSObject.Properties.Name -contains 'ArgumentList') {
        foreach ($argument in $Arguments) {
            [void]$startInfo.ArgumentList.Add($argument)
        }
    }
    else {
        $startInfo.Arguments = ConvertTo-ProcessArguments -Arguments $Arguments
    }
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.WorkingDirectory = (Get-Location).Path

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    [void]$process.Start()
    $stdOutTask = $process.StandardOutput.ReadToEndAsync()
    $stdErrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdOut = $stdOutTask.GetAwaiter().GetResult()
    $stdErr = $stdErrTask.GetAwaiter().GetResult()
    $durationMs = [int]((Get-Date) - $startTime).TotalMilliseconds
    $exitCode = $process.ExitCode

    Write-Progress -Activity $Activity -Status "Completed $ToolName" -PercentComplete 100 -Completed

    $logLevel = if ($exitCode -eq 0) { 'INFO' } else { 'ERROR' }
    $logMessage = if ($exitCode -eq 0) { "$ToolName completed successfully" } else { "$ToolName failed" }

    Write-StructuredLog -Session $Session -Level $logLevel -Message $logMessage -Tool $ToolName -Metadata @{
        exitCode   = $exitCode
        durationMs = $durationMs
        stdout     = $stdOut
        stderr     = $stdErr
    }

    if ($exitCode -ne 0 -and $ThrowOnError) {
        throw "$ToolName failed with exit code $exitCode"
    }

    return [PSCustomObject]@{
        ExitCode = $exitCode
        StdOut   = $stdOut
        StdErr   = $stdErr
    }
}

function Invoke-Curl {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [pscustomobject]$Session
    )

    return Invoke-ExternalTool -ToolPath 'curl' -Arguments $Arguments -Session $Session -ToolName 'curl' -Activity 'Downloading with curl'
}

function Invoke-7Zip {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [Parameter(Mandatory = $true)]
        [pscustomobject]$Session,

        [string]$SevenZipPath = '7z'
    )

    return Invoke-ExternalTool -ToolPath $SevenZipPath -Arguments $Arguments -Session $Session -ToolName '7zip' -Activity 'Extracting with 7-Zip'
}
