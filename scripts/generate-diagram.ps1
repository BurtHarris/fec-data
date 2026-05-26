$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$mermaidSource = Join-Path $repoRoot 'artifacts\diagrams\semantic_model_diagram.md'
$outputSvg = Join-Path $repoRoot 'artifacts\diagrams\semantic_model_diagram.svg'

$mermaidCli = Get-Command -Name mmdc -ErrorAction SilentlyContinue

if (-not $mermaidCli) {
    Write-Error 'mmdc was not found on PATH. Install Mermaid CLI before running this script.'
    exit 1
}

& $mermaidCli.Path -i $mermaidSource -o $outputSvg --backgroundColor transparent

Write-Host "Diagram regenerated: $outputSvg"