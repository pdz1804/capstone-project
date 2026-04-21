param(
    [string]$JMeterBin = "jmeter",
    [string]$TargetHost = "k2p-bkmind-learning-platform.com",
    [string]$Protocol = "https",
    [int]$Port = 443,
    [string]$ConcurrencyLevels = "5,10,20,30,40,50,60,80",
    [int]$Loops = 1,
    [int]$RampUpPerThreadSec = 3,
    [string]$UsersCsvPath = "",
    [string]$QueriesCsvPath = "",
    [switch]$EnableMutationApis,
    [string]$UploadFilePath = "",
    [double]$MaxErrorRatePct = 5.0,
    [double]$MaxP95LatencyMs = 15000.0,
    [int]$MinRequestsPerLabel = 10
)

function Resolve-JMeterExecutable {
    param([string]$Requested)

    if ($Requested -and (Test-Path $Requested)) {
        return (Resolve-Path $Requested).Path
    }

    $found = Get-Command $Requested -ErrorAction SilentlyContinue
    if ($found) {
        return $Requested
    }

    $candidates = @(
        @(
            "C:\apache-jmeter\bin\jmeter.bat",
            "C:\tools\apache-jmeter\bin\jmeter.bat",
            "$env:LOCALAPPDATA\Programs\JMeter\bin\jmeter.bat",
            "$env:ProgramFiles\ApacheJMeter\bin\jmeter.bat",
            "$env:ProgramFiles\apache-jmeter\bin\jmeter.bat",
            "$env:ProgramFiles(x86)\ApacheJMeter\bin\jmeter.bat"
        ) | Where-Object { $_ -and (Test-Path $_) }
    )

    if ($candidates.Count -gt 0) {
        return [string]$candidates[0]
    }

    throw "JMeter executable not found. Install Apache JMeter or pass -JMeterBin with full path to jmeter.bat."
}

function Get-PercentileValue {
    param(
        [double[]]$Values,
        [double]$Percentile
    )

    if (-not $Values -or $Values.Count -eq 0) {
        return 0
    }

    $sorted = @($Values | Sort-Object)
    $n = $sorted.Count
    if ($n -eq 1) {
        return [double]$sorted[0]
    }

    $position = ($Percentile / 100.0) * ($n - 1)
    $lowerIndex = [int][Math]::Floor($position)
    $upperIndex = [int][Math]::Ceiling($position)

    if ($lowerIndex -eq $upperIndex) {
        return [double]$sorted[$lowerIndex]
    }

    $weight = $position - $lowerIndex
    return [double]($sorted[$lowerIndex] + (($sorted[$upperIndex] - $sorted[$lowerIndex]) * $weight))
}

function Get-JtlLabelSummary {
    param(
        [string]$JtlPath,
        [int]$Threads,
        [int]$RampUp,
        [int]$Loops
    )

    if (-not (Test-Path $JtlPath)) {
        throw "JTL file not found for concurrency level ${Threads}: $JtlPath"
    }

    $rows = Import-Csv -Path $JtlPath -ErrorAction Stop
    if (-not $rows -or $rows.Count -eq 0) {
        return @()
    }

    $out = @()
    $groups = $rows | Group-Object -Property label

    foreach ($g in $groups) {
        $elapsed = @($g.Group | ForEach-Object { [double]$_.elapsed })
        $minTs = [double](($g.Group | Measure-Object -Property timeStamp -Minimum).Minimum)
        $maxTs = [double](($g.Group | Measure-Object -Property timeStamp -Maximum).Maximum)
        $durationSec = [Math]::Max((($maxTs - $minTs) / 1000.0), 1.0)

        $total = [int]$g.Count
        $failed = [int](($g.Group | Where-Object { $_.success -ne "true" }).Count)
        $errorRate = if ($total -gt 0) { ($failed * 100.0) / $total } else { 0 }
        $avg = [double](($elapsed | Measure-Object -Average).Average)
        $p95 = Get-PercentileValue -Values $elapsed -Percentile 95
        $p99 = Get-PercentileValue -Values $elapsed -Percentile 99
        $minLatency = [double](($elapsed | Measure-Object -Minimum).Minimum)
        $maxLatency = [double](($elapsed | Measure-Object -Maximum).Maximum)
        $throughput = $total / $durationSec

        $out += [pscustomobject]@{
            threads = $Threads
            ramp_up = $RampUp
            loops = $Loops
            label = [string]$g.Name
            total_requests = $total
            failed_requests = $failed
            error_rate_pct = [Math]::Round($errorRate, 4)
            avg_latency_ms = [Math]::Round($avg, 2)
            p95_latency_ms = [Math]::Round($p95, 2)
            p99_latency_ms = [Math]::Round($p99, 2)
            min_latency_ms = [Math]::Round($minLatency, 2)
            max_latency_ms = [Math]::Round($maxLatency, 2)
            throughput_rps = [Math]::Round($throughput, 4)
            duration_sec = [Math]::Round($durationSec, 2)
        }
    }

    return $out
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$testPlan = Join-Path $scriptDir "BKMind_Essential_APIs_Auth.jmx"
if (-not (Test-Path $testPlan)) {
    throw "Test plan not found: $testPlan"
}

if ([string]::IsNullOrWhiteSpace($UsersCsvPath)) {
    $UsersCsvPath = Join-Path $scriptDir "data\users.csv"
}
if ([string]::IsNullOrWhiteSpace($QueriesCsvPath)) {
    $QueriesCsvPath = Join-Path $scriptDir "data\queries.csv"
}
if ([string]::IsNullOrWhiteSpace($UploadFilePath)) {
    $UploadFilePath = Join-Path $scriptDir "data\sample_upload.md"
}
if (-not (Test-Path $UsersCsvPath)) {
    throw "Users CSV not found: $UsersCsvPath"
}
if (-not (Test-Path $QueriesCsvPath)) {
    throw "Queries CSV not found: $QueriesCsvPath"
}

$resolvedJMeter = Resolve-JMeterExecutable -Requested $JMeterBin
$resolvedJMeterCmd = if ($resolvedJMeter -eq "jmeter") { "jmeter" } else { '"' + $resolvedJMeter + '"' }
$runMutationApis = if ($EnableMutationApis) { "true" } else { "false" }

$levels = @($ConcurrencyLevels.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^\d+$' } | ForEach-Object { [int]$_ })
if (-not $levels -or $levels.Count -eq 0) {
    throw 'No valid concurrency levels. Example: -ConcurrencyLevels "5,10,20,30"'
}

$reportsDir = Join-Path $scriptDir "reports"
$concurrencyDir = Join-Path $reportsDir "concurrency"
$reportReadyDir = Join-Path $scriptDir "report-ready"
New-Item -ItemType Directory -Path $concurrencyDir -Force | Out-Null
New-Item -ItemType Directory -Path $reportReadyDir -Force | Out-Null

$batchTs = Get-Date -Format "yyyyMMdd_HHmmss"
$allRows = @()

Write-Host "Running API concurrency sweep..."
Write-Host "Target: ${Protocol}://${TargetHost}:${Port}"
Write-Host "JMeter executable: $resolvedJMeter"
Write-Host "Concurrency levels: $($levels -join ', ')"

$originalJvmArgs = $env:JVM_ARGS
$originalHeap = $env:HEAP

try {
    Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
    Remove-Item Env:HEAP -ErrorAction SilentlyContinue

foreach ($threads in $levels) {
    $rampUp = [Math]::Max($threads * $RampUpPerThreadSec, 1)
    $runName = "concurrency_${threads}_$batchTs"
    $jtlPath = Join-Path $concurrencyDir "$runName.jtl"
    $htmlPath = Join-Path $concurrencyDir $runName
    $runLogPath = Join-Path $concurrencyDir "$runName.jmeter.log"

    Write-Host ""
    Write-Host "Running concurrency level: threads=$threads, ramp_up=$rampUp, loops=$Loops"

    $args = @(
        "-n",
        "-t", $testPlan,
        "-l", $jtlPath,
        "-e",
        "-o", $htmlPath,
        "-j", $runLogPath,
        "-Jhost=$TargetHost",
        "-Jprotocol=$Protocol",
        "-Jport=$Port",
        "-Jthreads=$threads",
        "-Jramp_up=$rampUp",
        "-Jloops=$Loops",
        "-Jrun_mutation_apis=$runMutationApis",
        "-Jupload_file_path=$UploadFilePath",
        "-Jusers_csv=$UsersCsvPath",
        "-Jqueries_csv=$QueriesCsvPath",
        "-Jjmeter.save.saveservice.output_format=csv",
        "-Jjmeter.save.saveservice.assertion_results_failure_message=true",
        "-Jjmeter.save.saveservice.response_data.on_error=true",
        "-Jjmeter.save.saveservice.latency=true",
        "-Jjmeter.save.saveservice.connect_time=true",
        "-Jjmeter.save.saveservice.thread_counts=true",
        "-Jjmeter.save.saveservice.bytes=true",
        "-Jjmeter.save.saveservice.sent_bytes=true",
        "-Jjmeter.save.saveservice.hostname=true"
    )

    $escapedArgs = $args | ForEach-Object { '"' + ($_ -replace '"', '\\"') + '"' }
    $cmdLine = "echo.|$resolvedJMeterCmd $($escapedArgs -join ' ')"
    cmd /c $cmdLine
    if ($LASTEXITCODE -ne 0) {
        throw "Concurrency level $threads failed with exit code $LASTEXITCODE. JMeter log: $runLogPath"
    }

    if (-not (Test-Path $jtlPath)) {
        throw "Concurrency level $threads did not produce JTL output: $jtlPath. Check JMeter log: $runLogPath"
    }

    if ((Get-Item $jtlPath).Length -le 0) {
        throw "Concurrency level $threads produced an empty JTL output: $jtlPath. Check JMeter log: $runLogPath"
    }

    $allRows += Get-JtlLabelSummary -JtlPath $jtlPath -Threads $threads -RampUp $rampUp -Loops $Loops
}
}
finally {
    if ($null -eq $originalJvmArgs) {
        Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
    }
    else {
        $env:JVM_ARGS = $originalJvmArgs
    }

    if ($null -eq $originalHeap) {
        Remove-Item Env:HEAP -ErrorAction SilentlyContinue
    }
    else {
        $env:HEAP = $originalHeap
    }
}

$detailCsv = Join-Path $reportReadyDir "concurrency_labels_${batchTs}.csv"
$maxCsv = Join-Path $reportReadyDir "concurrency_max_supported_${batchTs}.csv"
$summaryMd = Join-Path $reportReadyDir "concurrency_summary_${batchTs}.md"

$allRows | Sort-Object label, threads | Export-Csv -Path $detailCsv -NoTypeInformation -Encoding UTF8

$maxRows = @()
$labelGroups = $allRows | Group-Object -Property label
foreach ($group in $labelGroups) {
    $rows = @($group.Group | Sort-Object threads)

    $eligible = @(
        $rows | Where-Object {
            $_.total_requests -ge $MinRequestsPerLabel -and
            $_.error_rate_pct -le $MaxErrorRatePct -and
            $_.p95_latency_ms -le $MaxP95LatencyMs
        }
    )

    $maxSupported = if ($eligible.Count -gt 0) { ($eligible | Sort-Object threads -Descending | Select-Object -First 1).threads } else { 0 }

    $firstFailure = $rows | Where-Object {
        $_.threads -gt $maxSupported -and (
            $_.total_requests -lt $MinRequestsPerLabel -or
            $_.error_rate_pct -gt $MaxErrorRatePct -or
            $_.p95_latency_ms -gt $MaxP95LatencyMs
        )
    } | Sort-Object threads | Select-Object -First 1

    $reason = ""
    if ($firstFailure) {
        $reasonParts = @()
        if ($firstFailure.total_requests -lt $MinRequestsPerLabel) { $reasonParts += "insufficient_samples" }
        if ($firstFailure.error_rate_pct -gt $MaxErrorRatePct) { $reasonParts += "error_rate_exceeded" }
        if ($firstFailure.p95_latency_ms -gt $MaxP95LatencyMs) { $reasonParts += "p95_exceeded" }
        $reason = ($reasonParts -join ",")
    }

    $maxRows += [pscustomobject]@{
        label = $group.Name
        max_supported_threads = $maxSupported
        threshold_max_error_rate_pct = $MaxErrorRatePct
        threshold_max_p95_latency_ms = $MaxP95LatencyMs
        threshold_min_requests = $MinRequestsPerLabel
        first_failure_threads = if ($firstFailure) { $firstFailure.threads } else { "" }
        first_failure_reason = $reason
    }
}

$maxRows | Sort-Object label | Export-Csv -Path $maxCsv -NoTypeInformation -Encoding UTF8

$md = @()
$md += "# API Maximum Concurrency Sweep"
$md += ""
$md += "- Target: ${Protocol}://${TargetHost}:${Port}"
$md += "- Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$md += "- Concurrency levels: $($levels -join ', ')"
$md += "- Loops per run: $Loops"
$md += "- Thresholds: error_rate <= $MaxErrorRatePct%, p95 <= $MaxP95LatencyMs ms, min_requests >= $MinRequestsPerLabel"
$md += ""
$md += "## Artifacts"
$md += ""
$md += "- Detailed per-label metrics by concurrency: $(Split-Path -Leaf $detailCsv)"
$md += "- Max supported threads by API label: $(Split-Path -Leaf $maxCsv)"
$md += ""
$md += "## Max Supported Concurrency (per API label)"
$md += ""
$md += "| API Label | Max Supported Threads | First Failure Threads | First Failure Reason |"
$md += "|---|---:|---:|---|"
foreach ($row in ($maxRows | Sort-Object label)) {
    $md += "| $($row.label) | $($row.max_supported_threads) | $($row.first_failure_threads) | $($row.first_failure_reason) |"
}

Set-Content -Path $summaryMd -Value $md -Encoding UTF8

Write-Host "Done."
Write-Host "Detailed CSV: $detailCsv"
Write-Host "Max-supported CSV: $maxCsv"
Write-Host "Summary markdown: $summaryMd"
Write-Host "Concurrency HTML reports: $concurrencyDir"

exit 0
