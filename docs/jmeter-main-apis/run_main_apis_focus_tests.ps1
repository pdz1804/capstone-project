param(
    [string]$JMeterBin = "jmeter",
    [string]$TargetHost = "k2p-bkmind-learning-platform.com",
    [string]$Protocol = "https",
    [int]$Port = 443,
    [int]$Threads = 5,
    [int]$RampUp = 30,
    [int]$Loops = 1,
    [switch]$RunSearchApis = $true,
    [switch]$RunPipelineApis = $true,
    [switch]$RunUploadApi = $true,
    [switch]$RunProcessApi = $true,
    [switch]$RunIndexApi = $true,
    [switch]$RunSearchTextApi = $true,
    [switch]$RunSearchBothApi = $true,
    [ValidateSet("retrieval_only", "retrieval_generation")]
    [string]$SearchModeText = "retrieval_generation",
    [ValidateSet("retrieval_only", "retrieval_generation")]
    [string]$SearchModeBoth = "retrieval_generation",
    [ValidateSet("shareMode.all", "shareMode.group", "shareMode.thread")]
    [string]$UsersShareMode = "shareMode.all",
    [string]$UsersCsvPath = "",
    [string]$UploadFilePath = "",
    [string]$UploadMimeType = "text/markdown",
    [ValidateSet("standard", "fast")]
    [string]$ProcessMode = "fast",
    [ValidateSet("standard", "fast")]
    [string]$IndexMode = "fast",
    [switch]$PipelineAllThreads,
    [int]$SetupTestUserCount = 9,
    [switch]$SkipAccountSetup,
    [int]$MaxRetries = 2,
    [double]$ErrorRateAlertPct = 5.0
)

function Resolve-JMeterExecutable {
    param([string]$Requested)

    if ($Requested -and (Test-Path $Requested)) {
        return (Resolve-Path $Requested).Path
    }

    $found = Get-Command $Requested -ErrorAction SilentlyContinue
    if ($found) {
        if ($found.Source -and (Test-Path $found.Source)) {
            return $found.Source
        }

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

    throw "JMeter executable not found. Install Apache JMeter or pass -JMeterBin with full path to jmeter executable."
}

function Resolve-JavaExecutable {
    $javaCmd = Get-Command java -ErrorAction SilentlyContinue
    if (-not $javaCmd) {
        throw "Java executable not found in PATH. Install Java 8+ and retry."
    }

    if ($javaCmd.Source -and (Test-Path $javaCmd.Source)) {
        return $javaCmd.Source
    }

    return "java"
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

function Convert-ToJMeterPath {
    param([string]$PathValue)
    return ($PathValue -replace '\\', '/')
}

function Get-JtlLabelSummary {
    param([string]$JtlPath)

    if (-not (Test-Path $JtlPath)) {
        throw "JTL not found: $JtlPath"
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
        $failed = [int](@($g.Group | Where-Object { $_.success -ne "true" }).Count)
        $errorRate = if ($total -gt 0) { ($failed * 100.0) / $total } else { 0 }
        $avg = [double](($elapsed | Measure-Object -Average).Average)
        $p95 = Get-PercentileValue -Values $elapsed -Percentile 95
        $p99 = Get-PercentileValue -Values $elapsed -Percentile 99

        $out += [pscustomobject]@{
            label = [string]$g.Name
            total_requests = $total
            failed_requests = $failed
            error_rate_pct = [Math]::Round($errorRate, 4)
            avg_latency_ms = [Math]::Round($avg, 2)
            p95_latency_ms = [Math]::Round($p95, 2)
            p99_latency_ms = [Math]::Round($p99, 2)
            throughput_rps = [Math]::Round(($total / $durationSec), 4)
            duration_sec = [Math]::Round($durationSec, 2)
        }
    }

    return $out
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$testPlan = Join-Path $scriptDir "BKMind_Main_APIs_Focus.jmx"
$dashboardProps = Join-Path $scriptDir "main_apis_reportgenerator.properties"
$dataDir = Join-Path $scriptDir "data"
$usersCsv = if ([string]::IsNullOrWhiteSpace($UsersCsvPath)) {
    Join-Path $dataDir "users.csv"
}
else {
    $UsersCsvPath
}
$queriesCsv = Join-Path $dataDir "main_queries.csv"
$uploadFile = if ([string]::IsNullOrWhiteSpace($UploadFilePath)) {
    Join-Path $dataDir "sample_upload.md"
}
else {
    $UploadFilePath
}
$reportsDir = Join-Path $scriptDir "reports"
$reportReadyDir = Join-Path $scriptDir "report-ready"
$setupScript = Join-Path (Join-Path $scriptDir "..\jmeter-experiments") "setup_test_accounts.ps1"

if (-not (Test-Path $testPlan)) { throw "Test plan not found: $testPlan" }
if (-not (Test-Path $dashboardProps)) { throw "Dashboard properties not found: $dashboardProps" }
if (-not (Test-Path $queriesCsv)) { throw "Queries CSV not found: $queriesCsv" }
if (-not (Test-Path $uploadFile)) { throw "Upload file not found: $uploadFile" }

if (-not $SkipAccountSetup) {
    if (-not (Test-Path $setupScript)) {
        throw "Account setup script not found: $setupScript"
    }

    Write-Host "[1/3] Provisioning/verifying users CSV..."
    & $setupScript `
        -TargetHost $TargetHost `
        -Protocol $Protocol `
        -Port $Port `
        -TestUserCount $SetupTestUserCount `
        -OutputCsv $usersCsv

    if ($LASTEXITCODE -ne 0) {
        throw "Account setup failed with exit code $LASTEXITCODE"
    }
}
else {
    Write-Host "[1/3] Skipping account setup (as requested)."
}

if (-not (Test-Path $usersCsv)) {
    throw "Users CSV not found: $usersCsv"
}

$resolvedJMeter = Resolve-JMeterExecutable -Requested $JMeterBin
$useJavaLauncher = $false
$javaExe = $null
$jmeterJar = $null

if ($resolvedJMeter -match '\.jar$') {
    $jmeterJar = $resolvedJMeter
    $useJavaLauncher = $true
}
elseif ($resolvedJMeter -match '\.bat$') {
    $candidateJar = Join-Path (Split-Path -Parent $resolvedJMeter) "ApacheJMeter.jar"
    if (Test-Path $candidateJar) {
        $jmeterJar = $candidateJar
        $useJavaLauncher = $true
    }
}

if ($useJavaLauncher) {
    $javaExe = Resolve-JavaExecutable
}

$launcherDescription = if ($useJavaLauncher) {
    "$javaExe -Djava.awt.headless=true -jar $jmeterJar"
}
else {
    $resolvedJMeter
}

New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null
New-Item -ItemType Directory -Path $reportReadyDir -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$jtl = Join-Path $reportsDir "main_apis_focus_$timestamp.jtl"
$html = Join-Path $reportsDir "main_apis_focus_$timestamp"
$runLog = Join-Path $reportsDir "main_apis_focus_$timestamp.jmeter.log"
$runtimeProps = Join-Path $reportsDir "main_apis_focus_$timestamp.runtime.properties"

$originalJvmArgs = $env:JVM_ARGS
$originalHeap = $env:HEAP

$runSearchValue = if ($RunSearchApis) { "true" } else { "false" }
$runPipelineValue = if ($RunPipelineApis) { "true" } else { "false" }
$runUploadValue = if ($RunUploadApi) { "true" } else { "false" }
$runProcessValue = if ($RunProcessApi) { "true" } else { "false" }
$runIndexValue = if ($RunIndexApi) { "true" } else { "false" }
$runSearchTextValue = if ($RunSearchTextApi) { "true" } else { "false" }
$runSearchBothValue = if ($RunSearchBothApi) { "true" } else { "false" }
$pipelineFirstThreadOnlyValue = if ($PipelineAllThreads) { "false" } else { "true" }

$runtimePropsContent = @(
    "host=$TargetHost",
    "protocol=$Protocol",
    "port=$Port",
    "threads=$Threads",
    "ramp_up=$RampUp",
    "loops=$Loops",
    "users_csv=$(Convert-ToJMeterPath -PathValue $usersCsv)",
    "queries_csv=$(Convert-ToJMeterPath -PathValue $queriesCsv)",
    "upload_file_path=$(Convert-ToJMeterPath -PathValue $uploadFile)",
    "users_share_mode=$UsersShareMode",
    "upload_mime_type=$UploadMimeType",
    "run_search_apis=$runSearchValue",
    "run_search_text_api=$runSearchTextValue",
    "run_search_both_api=$runSearchBothValue",
    "search_mode_text=$SearchModeText",
    "search_mode_both=$SearchModeBoth",
    "run_pipeline_apis=$runPipelineValue",
    "pipeline_first_thread_only=$pipelineFirstThreadOnlyValue",
    "run_upload_api=$runUploadValue",
    "run_process_api=$runProcessValue",
    "process_mode=$ProcessMode",
    "run_index_api=$runIndexValue",
    "index_mode=$IndexMode",
    "jmeter.save.saveservice.output_format=csv",
    "jmeter.save.saveservice.bytes=true",
    "jmeter.save.saveservice.sent_bytes=true",
    "jmeter.save.saveservice.label=true",
    "jmeter.save.saveservice.latency=true",
    "jmeter.save.saveservice.response_code=true",
    "jmeter.save.saveservice.response_message=true",
    "jmeter.save.saveservice.successful=true",
    "jmeter.save.saveservice.thread_counts=true",
    "jmeter.save.saveservice.thread_name=true",
    "jmeter.save.saveservice.time=true",
    "jmeter.save.saveservice.connect_time=true",
    "jmeter.save.saveservice.assertion_results_failure_message=true",
    "jmeter.save.saveservice.timestamp_format=ms"
)
Set-Content -Path $runtimeProps -Value $runtimePropsContent -Encoding UTF8

Write-Host "[2/3] Running focused main APIs test..."
Write-Host "Target: ${Protocol}://${TargetHost}:${Port}"
Write-Host "Threads: $Threads | RampUp: $RampUp | Loops: $Loops"
Write-Host "Search APIs: $runSearchValue | Pipeline APIs: $runPipelineValue"
Write-Host "Pipeline execution mode: $(if ($PipelineAllThreads) { 'all threads' } else { 'first thread only' })"
Write-Host "Upload MIME type: $UploadMimeType | Process mode: $ProcessMode | Index mode: $IndexMode"
Write-Host "Launcher: $launcherDescription"

$attempt = 0
$runSucceeded = $false

try {
    Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
    Remove-Item Env:HEAP -ErrorAction SilentlyContinue

    while ($attempt -le $MaxRetries -and -not $runSucceeded) {
        if ($attempt -gt 0) {
            Write-Warning "Retry attempt $attempt/$MaxRetries due to previous failure."
        }

        if (Test-Path $jtl) { Remove-Item $jtl -Force }
        if (Test-Path $runLog) { Remove-Item $runLog -Force }
        if (Test-Path $html) { Remove-Item $html -Recurse -Force }

        $args = @(
            "-q", $dashboardProps,
            "-q", $runtimeProps,
            "-n",
            "-t", $testPlan,
            "-l", $jtl,
            "-e",
            "-o", $html,
            "-j", $runLog
        )

        if ($useJavaLauncher) {
            $javaArgs = @("-Djava.awt.headless=true", "-jar", $jmeterJar) + $args
            & $javaExe @javaArgs
        }
        else {
            $escapedArgs = $args | ForEach-Object { '"' + ($_ -replace '"', '\\"') + '"' }
            $cmdLine = "echo.|`"$resolvedJMeter`" $($escapedArgs -join ' ')"
            cmd /c $cmdLine
        }

        if ($LASTEXITCODE -eq 0 -and (Test-Path $jtl) -and ((Get-Item $jtl).Length -gt 0)) {
            $runSucceeded = $true
        }
        else {
            $attempt++
        }
    }

    if (-not $runSucceeded) {
        throw "Focused main APIs test failed after retries. Check JMeter log: $runLog"
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

Write-Host "[3/3] Building focused KPI summary..."
$labelsCsv = Join-Path $reportReadyDir "main_apis_labels_$timestamp.csv"
$summaryMd = Join-Path $reportReadyDir "main_apis_summary_$timestamp.md"

$labelRows = Get-JtlLabelSummary -JtlPath $jtl
$labelRows |
    Sort-Object -Property @{Expression='error_rate_pct';Descending=$true}, @{Expression='failed_requests';Descending=$true} |
    Export-Csv -Path $labelsCsv -NoTypeInformation -Encoding UTF8

$highError = @($labelRows | Where-Object { $_.error_rate_pct -ge $ErrorRateAlertPct } | Sort-Object error_rate_pct -Descending)

$md = @()
$md += "# Main APIs Focus Summary"
$md += ""
$md += "- Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$md += "- Target: ${Protocol}://${TargetHost}:${Port}"
$md += "- Threads: $Threads | RampUp: $RampUp | Loops: $Loops"
$md += "- Search APIs enabled: $runSearchValue"
$md += "- Search text API enabled: $runSearchTextValue | mode=$SearchModeText"
$md += "- Search both API enabled: $runSearchBothValue | mode=$SearchModeBoth"
$md += "- Pipeline APIs enabled: $runPipelineValue"
$md += "- Users share mode: $UsersShareMode"
$md += "- Retry policy used: max_retries=$MaxRetries"
$md += ""
$md += "## Label KPIs"
$md += ""
$md += "| Label | Total | Failed | Error % | Avg (ms) | P95 (ms) | P99 (ms) | Throughput (req/s) |"
$md += "|---|---:|---:|---:|---:|---:|---:|---:|"
foreach ($r in ($labelRows | Sort-Object -Property @{Expression='error_rate_pct';Descending=$true}, @{Expression='failed_requests';Descending=$true})) {
    $md += "| $($r.label) | $($r.total_requests) | $($r.failed_requests) | $($r.error_rate_pct) | $($r.avg_latency_ms) | $($r.p95_latency_ms) | $($r.p99_latency_ms) | $($r.throughput_rps) |"
}
$md += ""
$md += "## High-Error APIs (>= $ErrorRateAlertPct%)"
$md += ""
if ($highError.Count -eq 0) {
    $md += "- None"
}
else {
    foreach ($r in $highError) {
        $md += "- $($r.label): error_rate=$($r.error_rate_pct)% ($($r.failed_requests)/$($r.total_requests))"
    }
}
$md += ""
$md += "Artifacts:"
$md += "- JTL: $jtl"
$md += "- HTML dashboard: $html"
$md += "- JMeter log: $runLog"
$md += "- Runtime properties: $runtimeProps"
$md += "- Label summary CSV: $labelsCsv"

Set-Content -Path $summaryMd -Value $md -Encoding UTF8

Write-Host "Done."
Write-Host "JTL: $jtl"
Write-Host "HTML report: $html"
Write-Host "JMeter log: $runLog"
Write-Host "Runtime properties: $runtimeProps"
Write-Host "Label summary CSV: $labelsCsv"
Write-Host "Summary markdown: $summaryMd"

exit 0
