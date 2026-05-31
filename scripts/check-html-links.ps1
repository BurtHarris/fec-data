# check-html-links.ps1
# Validate href links in repository HTML artifacts.
#
# Defaults:
# - Scans ./artifacts/**/*.html
# - Checks local relative paths and remote http/https URLs
# - Writes a JSON report to ./tmp/html_link_check_artifacts.json
# - Exits non-zero when any broken links are found
#
# Run from repo root:
#   .\scripts\check-html-links.ps1
#
# Optional examples:
#   .\scripts\check-html-links.ps1 -RootPath .\artifacts\exploration
#   .\scripts\check-html-links.ps1 -SkipRemote

[CmdletBinding()]
param(
    [Parameter()]
    [string]$RootPath = "artifacts",

    [Parameter()]
    [string]$OutputJson = "tmp/html_link_check_artifacts.json",

    [Parameter()]
    [int]$TimeoutSec = 20,

    [Parameter()]
    [switch]$SkipRemote
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Get-HrefsFromHtml {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath
    )

    $content = Get-Content -LiteralPath $FilePath -Raw
    $pattern = 'href\s*=\s*"([^"]+)"|href\s*=\s*''([^'']+)'''
    $matches = [regex]::Matches($content, $pattern)

    $links = @()
    foreach ($m in $matches) {
        $href = if ($m.Groups[1].Success) { $m.Groups[1].Value } else { $m.Groups[2].Value }
        if ([string]::IsNullOrWhiteSpace($href)) {
            continue
        }

        $links += [pscustomobject]@{
            source_file = $FilePath
            href        = $href
        }
    }

    return $links
}

function Test-RemoteUrl {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,

        [Parameter(Mandatory = $true)]
        [int]$TimeoutSec
    )

    $status = $null
    $ok = $false
    $errorText = ""

    try {
        $resp = Invoke-WebRequest -Uri $Url -Method Head -MaximumRedirection 5 -TimeoutSec $TimeoutSec
        $status = [int]$resp.StatusCode
        $ok = $status -ge 200 -and $status -lt 400
    }
    catch {
        try {
            $resp = Invoke-WebRequest -Uri $Url -Method Get -MaximumRedirection 5 -TimeoutSec $TimeoutSec
            $status = [int]$resp.StatusCode
            $ok = $status -ge 200 -and $status -lt 400
        }
        catch {
            $errorText = $_.Exception.Message
            if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
                $status = [int]$_.Exception.Response.StatusCode
            }
        }
    }

    return [pscustomobject]@{
        ok     = $ok
        status = $status
        error  = $errorText
    }
}

$repoRoot = Get-RepoRoot
$scanRoot = if ([System.IO.Path]::IsPathRooted($RootPath)) {
    $RootPath
}
else {
    Join-Path $repoRoot $RootPath
}

if (-not (Test-Path -LiteralPath $scanRoot)) {
    throw "Scan root not found: $scanRoot"
}

$htmlFiles = Get-ChildItem -Path $scanRoot -Recurse -File -Filter *.html
$allLinks = @()
foreach ($file in $htmlFiles) {
    $allLinks += Get-HrefsFromHtml -FilePath $file.FullName
}

$results = @()
foreach ($entry in $allLinks) {
    $href = $entry.href.Trim()

    if ($href.StartsWith("#") -or $href -eq "." -or $href -eq "..") {
        $results += [pscustomobject]@{
            source_file = $entry.source_file
            href        = $href
            kind        = "anchor"
            ok          = $true
            status      = ""
            error       = ""
        }
        continue
    }

    if ($href -match '^(mailto:|tel:|javascript:|data:)') {
        $results += [pscustomobject]@{
            source_file = $entry.source_file
            href        = $href
            kind        = "skip"
            ok          = $true
            status      = ""
            error       = ""
        }
        continue
    }

    if ($href -match '^(https?://)') {
        if ($SkipRemote) {
            $results += [pscustomobject]@{
                source_file = $entry.source_file
                href        = $href
                kind        = "remote"
                ok          = $true
                status      = ""
                error       = "skipped"
            }
        }
        else {
            $remoteResult = Test-RemoteUrl -Url $href -TimeoutSec $TimeoutSec
            $results += [pscustomobject]@{
                source_file = $entry.source_file
                href        = $href
                kind        = "remote"
                ok          = $remoteResult.ok
                status      = if ($remoteResult.status) { $remoteResult.status } else { "" }
                error       = $remoteResult.error
            }
        }
        continue
    }

    $pathOnly = ($href -split '[?#]', 2)[0]
    $baseDir = Split-Path -Parent $entry.source_file
    $candidate = Join-Path $baseDir $pathOnly
    $exists = Test-Path -LiteralPath $candidate

    $results += [pscustomobject]@{
        source_file = $entry.source_file
        href        = $href
        kind        = "local"
        ok          = $exists
        status      = ""
        error       = if ($exists) { "" } else { "Missing: $candidate" }
    }
}

$outputPath = if ([System.IO.Path]::IsPathRooted($OutputJson)) {
    $OutputJson
}
else {
    Join-Path $repoRoot $OutputJson
}

$outputDir = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$results | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $outputPath -Encoding UTF8

$total = $results.Count
$broken = @($results | Where-Object { -not $_.ok })
$brokenCount = $broken.Count

Write-Host "Link report: $outputPath"
Write-Host "Checked links: $total"
Write-Host "Broken links: $brokenCount"

if ($brokenCount -gt 0) {
    $broken |
        Select-Object source_file, href, kind, status, error |
        Format-Table -AutoSize |
        Out-String |
        Write-Host

    exit 1
}

exit 0
