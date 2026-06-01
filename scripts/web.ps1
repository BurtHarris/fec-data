[CmdletBinding()]
param(
    [string]$HostName = '127.0.0.1',
    [int]$Port = 8787,
    [switch]$Reload,
    [switch]$NoSync,
    [switch]$NoOpen,
    [switch]$ForceStopPort
)

$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

function Get-PidFilePath([string]$repoRoot) {
    $tmpDir = Join-Path $repoRoot 'tmp'
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    return (Join-Path $tmpDir 'ops-web.pid')
}

function Get-ProcessCommandLine([int]$pid) {
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pid" -ErrorAction Stop
        return $proc.CommandLine
    } catch {
        return $null
    }
}

function Stop-ProcessIfOpsWeb([int]$pid, [switch]$Force) {
    $cmd = Get-ProcessCommandLine -pid $pid
    $looksLikeOpsWeb = $false
    if ($cmd) {
        $looksLikeOpsWeb = ($cmd -match 'uvicorn' -or $cmd -match 'ops-web' -or $cmd -match 'pipeline\\.web' -or $cmd -match 'pipeline/web')
    }

    if (-not $looksLikeOpsWeb -and -not $Force) {
        throw "Port/PID $pid is in use by a non-ops-web process. Re-run with -ForceStopPort to terminate it, or pick a different -Port. CommandLine: $cmd"
    }

    try {
        Stop-Process -Id $pid -Force -ErrorAction Stop
    } catch {
        # If it died between checks, ignore.
    }
}

$repoRoot = Get-RepoRoot
Set-Location $repoRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv not found on PATH. Install uv, then run 'uv sync' from repo root."
}

$pidFile = Get-PidFilePath -repoRoot $repoRoot

# 1) Stop the previously-started ops-web process (if any).
if (Test-Path $pidFile) {
    $raw = (Get-Content -Path $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $oldPid = 0
    if ([int]::TryParse(($raw | Out-String).Trim(), [ref]$oldPid) -and $oldPid -gt 0) {
        try {
            Stop-ProcessIfOpsWeb -pid $oldPid -Force:$ForceStopPort
        } catch {
            # If we can't safely stop it, surface the error and keep the PID file for debugging.
            throw
        }
    }
    Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
}

# 2) If something is still listening on the port, stop it if it looks like ops-web.
try {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($listener -and $listener.OwningProcess -gt 0) {
        Stop-ProcessIfOpsWeb -pid $listener.OwningProcess -Force:$ForceStopPort
    }
} catch {
    # Get-NetTCPConnection may be unavailable in some environments; ignore.
}

if (-not $NoSync) {
    & uv sync | Out-Host
}

$args = @('run', 'ops-web', '--host', $HostName, '--port', $Port)
if ($Reload) { $args += '--reload' }

$proc = Start-Process -FilePath 'uv' -ArgumentList $args -WorkingDirectory $repoRoot -PassThru
Set-Content -Path $pidFile -Value $proc.Id -Encoding ascii

# Wait for readiness (best-effort), then open browser.
$baseUrl = "http://$HostName`:$Port"
$healthUrl = "$baseUrl/healthz"
$deadline = (Get-Date).AddSeconds(20)
while ((Get-Date) -lt $deadline) {
    try {
        Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2 | Out-Null
        break
    } catch {
        Start-Sleep -Milliseconds 300
    }
}

if (-not $NoOpen) {
    Start-Process $baseUrl
}

Write-Host "ops-web running (pid $($proc.Id)) at $baseUrl"