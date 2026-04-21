param(
    [switch]$PurgeReportReady
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$reportsDir = Join-Path $scriptDir "reports"
$reportReadyDir = Join-Path $scriptDir "report-ready"

New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null
New-Item -ItemType Directory -Path $reportReadyDir -Force | Out-Null

$summaryPatterns = @("summary_*.csv", "summary_labels_*.csv", "summary_*.md")
foreach ($pattern in $summaryPatterns) {
    Get-ChildItem -Path $reportsDir -File -Filter $pattern -ErrorAction SilentlyContinue |
        Move-Item -Destination $reportReadyDir -Force
}

Get-ChildItem -Path $reportsDir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force

$logFile = Join-Path $scriptDir "jmeter.log"
if (Test-Path $logFile) {
    Remove-Item $logFile -Force
}

if ($PurgeReportReady) {
    Get-ChildItem -Path $reportReadyDir -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
}

Write-Host "Cleanup complete."
Write-Host "reports/: raw artifacts removed"
Write-Host "report-ready/: summary files preserved"

exit 0
