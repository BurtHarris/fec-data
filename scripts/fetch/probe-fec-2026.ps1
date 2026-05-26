#!/usr/bin/env pwsh
# =============================================================================
# probe-fec-2026.ps1
#
# Probes FEC bulk-download server for 2026 cycle file availability,
# reporting ETag, Last-Modified, and Content-Length for each file.
#
# Designed to be run as a PowerShell background job so the task can be
# monitored via Copilot CLI's /tasks "Add external job" feature.
#
# Usage:
#   # Run directly
#   .\scripts\fetch\probe-fec-2026.ps1
#
#   # Run as a trackable background job
#   $job = Start-Job -FilePath .\scripts\fetch\probe-fec-2026.ps1
#   Write-Host "Job ID: $($job.Id)  —  use this in Copilot /tasks > Add external job"
# =============================================================================

$cycle = "2026"
$yy    = $cycle.Substring(2)
$baseUrl = "https://www.fec.gov/files/bulk-downloads/$cycle"

$files = @(
    @{ Name = "weball$yy"; Desc = "Candidate summary totals"                 }
    @{ Name = "indiv$yy";  Desc = "Individual contributions (Schedule A)"    }
    @{ Name = "oppexp$yy"; Desc = "Operating expenditures (Schedule B)"      }
    @{ Name = "pas2$yy";   Desc = "Committee-to-committee contributions"     }
    @{ Name = "oth$yy";    Desc = "Inter-committee transfers"                }
    @{ Name = "cm$yy";     Desc = "Committee master file"                    }
    @{ Name = "cn$yy";     Desc = "Candidate master file"                    }
)

Write-Output "=== FEC 2026 Bulk File Availability Probe ==="
Write-Output "Base URL : $baseUrl"
Write-Output "Started  : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Output ""

$results = @()

foreach ($f in $files) {
    $url = "$baseUrl/$($f.Name).zip"
    Write-Output "[CHECK] $($f.Name).zip  ($($f.Desc))"

    try {
        $resp = Invoke-WebRequest -Uri $url -Method Head -UseBasicParsing -TimeoutSec 15
        $size = ($resp.Headers['Content-Length'] | Select-Object -First 1)
        $etag = ($resp.Headers['ETag'] | Select-Object -First 1)
        $modified = ($resp.Headers['Last-Modified'] | Select-Object -First 1)

        $sizeMb = if ($size) { [math]::Round([long]$size / 1MB, 1) } else { "?" }

        Write-Output "  Status : $($resp.StatusCode)"
        Write-Output "  Size   : $sizeMb MB  ($size bytes)"
        Write-Output "  ETag   : $etag"
        Write-Output "  Modified: $modified"

        $results += [PSCustomObject]@{
            File     = "$($f.Name).zip"
            Desc     = $f.Desc
            Status   = $resp.StatusCode
            SizeMB   = $sizeMb
            ETag     = $etag
            Modified = $modified
        }
    }
    catch {
        Write-Output "  ERROR: $($_.Exception.Message)"
        $results += [PSCustomObject]@{
            File    = "$($f.Name).zip"
            Desc    = $f.Desc
            Status  = "ERROR"
            SizeMB  = 0
            ETag    = ""
            Modified = ""
        }
    }

    Write-Output ""
    Start-Sleep -Seconds 1   # pace requests; also keeps the job alive long enough to attach
}

Write-Output "=== Summary ==="
$results | Format-Table -AutoSize

$totalMb = ($results | Where-Object { $_.SizeMB -ne "?" } | Measure-Object -Property SizeMB -Sum).Sum
Write-Output "Total available: $totalMb MB"
Write-Output "Completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
