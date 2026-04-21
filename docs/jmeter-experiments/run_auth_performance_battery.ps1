param(
    [string]$JMeterBin = "jmeter",
    [string]$TargetHost = "k2p-bkmind-learning-platform.com",
    [string]$Protocol = "https",
    [int]$Port = 443,
    [ValidateSet("quick", "standard", "full")]
    [string]$Profile = "standard",
    [string]$RunId = "",
    [switch]$RerunCompletedScenarios,
    [switch]$SkipAccountSetup,
    [string]$AdminEmail = "admin@local.dev",
    [string]$AdminPassword = "quangphu1804",
    [int]$TestUserCount = 9,
    [string]$TestUserPrefix = "perfuser",
    [string]$TestUserPassword = "LoadTest@2026!",
    [string]$UsersCsvPath = "",
    [string]$QueriesCsvPath = "",
    [switch]$EnableMutationApis,
    [string]$UploadFilePath = "",
    [switch]$AnalyzeWithBedrock,
    [string]$BedrockModelId = "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    [string]$BedrockRegion = "us-west-2",
    [switch]$FailIfBedrockAnalysisFails
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

    # Linear interpolation between nearest ranks for stable percentile estimates.
    $position = ($Percentile / 100.0) * ($n - 1)
    $lowerIndex = [int][Math]::Floor($position)
    $upperIndex = [int][Math]::Ceiling($position)

    if ($lowerIndex -eq $upperIndex) {
        return [double]$sorted[$lowerIndex]
    }

    $weight = $position - $lowerIndex
    return [double]($sorted[$lowerIndex] + (($sorted[$upperIndex] - $sorted[$lowerIndex]) * $weight))
}

function Get-JtlSummary {
    param(
        [string]$Scenario,
        [string]$JtlPath
    )

    if (-not (Test-Path $JtlPath)) {
        throw "JTL file not found for scenario ${Scenario}: $JtlPath"
    }

    $rows = Import-Csv -Path $JtlPath -ErrorAction Stop
    if (-not $rows -or $rows.Count -eq 0) {
        return [pscustomobject]@{
            scenario = $Scenario
            total_requests = 0
            failed_requests = 0
            error_rate_pct = 0
            avg_latency_ms = 0
            p95_latency_ms = 0
            p99_latency_ms = 0
            min_latency_ms = 0
            max_latency_ms = 0
            throughput_rps = 0
            duration_sec = 0
        }
    }

    $elapsed = @($rows | ForEach-Object { [double]$_.elapsed })
    $minTs = [double](($rows | Measure-Object -Property timeStamp -Minimum).Minimum)
    $maxTs = [double](($rows | Measure-Object -Property timeStamp -Maximum).Maximum)
    $durationSec = [Math]::Max((($maxTs - $minTs) / 1000.0), 1.0)

    $total = [int]$rows.Count
    $failed = [int](($rows | Where-Object { $_.success -ne "true" }).Count)
    $errorRate = if ($total -gt 0) { ($failed * 100.0) / $total } else { 0 }
    $avg = [double](($elapsed | Measure-Object -Average).Average)
    $p95 = Get-PercentileValue -Values $elapsed -Percentile 95
    $p99 = Get-PercentileValue -Values $elapsed -Percentile 99
    $minLatency = [double](($elapsed | Measure-Object -Minimum).Minimum)
    $maxLatency = [double](($elapsed | Measure-Object -Maximum).Maximum)
    $throughput = $total / $durationSec

    return [pscustomobject]@{
        scenario = $Scenario
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

function Get-JtlLabelSummary {
    param(
        [string]$Scenario,
        [string]$JtlPath
    )

    if (-not (Test-Path $JtlPath)) {
        throw "JTL file not found for scenario ${Scenario}: $JtlPath"
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
            scenario = $Scenario
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

function Get-ScenarioSet {
    param([string]$ChosenProfile)

    $quick = @(
        [pscustomobject]@{ Name = "S01_smoke"; Threads = 5; RampUp = 20; Loops = 1 },
        [pscustomobject]@{ Name = "S02_load"; Threads = 20; RampUp = 90; Loops = 2 }
    )

    $standard = @(
        [pscustomobject]@{ Name = "S01_smoke"; Threads = 5; RampUp = 20; Loops = 1 },
        [pscustomobject]@{ Name = "S02_load"; Threads = 20; RampUp = 90; Loops = 3 },
        [pscustomobject]@{ Name = "S03_concurrency"; Threads = 30; RampUp = 60; Loops = 2 },
        [pscustomobject]@{ Name = "S04_stress"; Threads = 20; RampUp = 90; Loops = 2 }
    )

    $full = @(
        [pscustomobject]@{ Name = "S01_smoke"; Threads = 5; RampUp = 20; Loops = 1 },
        [pscustomobject]@{ Name = "S02_load"; Threads = 20; RampUp = 90; Loops = 3 },
        [pscustomobject]@{ Name = "S03_concurrency"; Threads = 40; RampUp = 60; Loops = 3 },
        [pscustomobject]@{ Name = "S04_stress"; Threads = 70; RampUp = 90; Loops = 2 },
        [pscustomobject]@{ Name = "S05_spike"; Threads = 110; RampUp = 10; Loops = 1 },
        [pscustomobject]@{ Name = "S06_endurance"; Threads = 25; RampUp = 120; Loops = 8 }
    )

    switch ($ChosenProfile) {
        "quick" { return $quick }
        "full" { return $full }
        default { return $standard }
    }
}

function Get-BedrockAnalysisPrompt {
    param(
        [string]$SummaryCsvPath,
        [string]$LabelCsvPath,
        [string]$Target,
        [string]$ProfileName
    )

    $summaryCsv = Get-Content -Path $SummaryCsvPath -Raw -Encoding UTF8
    $labelCsv = Get-Content -Path $LabelCsvPath -Raw -Encoding UTF8

    return @"
You are a senior performance engineer.
Analyze these JMeter performance results and produce:
1) Executive summary (5-8 lines)
2) Top bottleneck APIs by p95/p99 and error rate
3) Observed tail-latency explanation (avg vs p95/p99)
4) Concrete tuning recommendations (backend, infra, query, timeout, concurrency)
5) Suggested next test matrix with exact thread/ramp/loop values

Context:
- Target: $Target
- Profile: $ProfileName

Scenario summary CSV:
$summaryCsv

Per-label summary CSV:
$labelCsv
"@
}

function Invoke-BedrockSummaryAnalysis {
    param(
        [string]$SummaryCsvPath,
        [string]$LabelCsvPath,
        [string]$OutputMarkdownPath,
        [string]$ModelId,
        [string]$Region,
        [string]$Target,
        [string]$ProfileName
    )

    $awsCommand = Get-Command aws -ErrorAction SilentlyContinue
    if (-not $awsCommand) {
        throw "AWS CLI is not available in PATH. Install/configure AWS CLI before using -AnalyzeWithBedrock."
    }

    $prompt = Get-BedrockAnalysisPrompt `
        -SummaryCsvPath $SummaryCsvPath `
        -LabelCsvPath $LabelCsvPath `
        -Target $Target `
        -ProfileName $ProfileName

    $payloadObject = @{
        anthropic_version = "bedrock-2023-05-31"
        max_tokens = 2500
        temperature = 0.1
        messages = @(
            @{
                role = "user"
                content = @(
                    @{
                        type = "text"
                        text = $prompt
                    }
                )
            }
        )
    }

    $payloadJson = $payloadObject | ConvertTo-Json -Depth 12
    $tempId = [Guid]::NewGuid().ToString("N")
    $payloadPath = Join-Path $env:TEMP "bedrock_payload_$tempId.json"
    $responsePath = Join-Path $env:TEMP "bedrock_response_$tempId.json"

    try {
        Set-Content -Path $payloadPath -Value $payloadJson -Encoding UTF8

        & aws bedrock-runtime invoke-model `
            --region $Region `
            --model-id $ModelId `
            --content-type "application/json" `
            --accept "application/json" `
            --body ("fileb://" + $payloadPath) `
            $responsePath | Out-Null

        if ($LASTEXITCODE -ne 0) {
            throw "Bedrock invoke-model failed with exit code $LASTEXITCODE."
        }

        $responseRaw = Get-Content -Path $responsePath -Raw -Encoding UTF8
        $responseObj = $responseRaw | ConvertFrom-Json

        $analysisText = ""
        if ($responseObj.content) {
            $textParts = @($responseObj.content | Where-Object { $_.type -eq "text" } | ForEach-Object { $_.text })
            $analysisText = ($textParts -join "`n`n").Trim()
        }
        elseif ($responseObj.completion) {
            $analysisText = [string]$responseObj.completion
        }

        if ([string]::IsNullOrWhiteSpace($analysisText)) {
            throw "Bedrock response did not contain analysis text."
        }

        $md = @()
        $md += "# Bedrock Analysis of Performance Results"
        $md += ""
        $md += "- Model: $ModelId"
        $md += "- Region: $Region"
        $md += "- Target: $Target"
        $md += "- Profile: $ProfileName"
        $md += "- Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        $md += ""
        $md += $analysisText

        Set-Content -Path $OutputMarkdownPath -Value $md -Encoding UTF8
    }
    finally {
        if (Test-Path $payloadPath) {
            Remove-Item $payloadPath -Force
        }
        if (Test-Path $responsePath) {
            Remove-Item $responsePath -Force
        }
    }
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
if (-not (Test-Path $QueriesCsvPath)) {
    throw "Queries CSV not found: $QueriesCsvPath"
}

$totalSteps = if ($AnalyzeWithBedrock) { 4 } else { 3 }

if (-not $SkipAccountSetup) {
    $setupScript = Join-Path $scriptDir "setup_test_accounts.ps1"
    if (-not (Test-Path $setupScript)) {
        throw "Account setup script not found: $setupScript"
    }

    Write-Host "[1/$totalSteps] Provisioning/verifying test accounts..."
    & $setupScript `
        -TargetHost $TargetHost `
        -Protocol $Protocol `
        -Port $Port `
        -AdminEmail $AdminEmail `
        -AdminPassword $AdminPassword `
        -TestUserCount $TestUserCount `
        -TestUserPrefix $TestUserPrefix `
        -TestUserPassword $TestUserPassword `
        -OutputCsv $UsersCsvPath

    if ($LASTEXITCODE -ne 0) {
        throw "Account setup failed with exit code $LASTEXITCODE"
    }
}
else {
    Write-Host "[1/$totalSteps] Skipping account setup (as requested)."
}

if (-not (Test-Path $UsersCsvPath)) {
    throw "Users CSV not found: $UsersCsvPath"
}

$resolvedJMeter = Resolve-JMeterExecutable -Requested $JMeterBin
$resolvedJMeterCmd = if ($resolvedJMeter -eq "jmeter") { "jmeter" } else { '"' + $resolvedJMeter + '"' }
$scenarios = Get-ScenarioSet -ChosenProfile $Profile
$runMutationApis = if ($EnableMutationApis) { "true" } else { "false" }

$reportsDir = Join-Path $scriptDir "reports"
$reportReadyDir = Join-Path $scriptDir "report-ready"
New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null
New-Item -ItemType Directory -Path $reportReadyDir -Force | Out-Null
$batchTs = if ([string]::IsNullOrWhiteSpace($RunId)) { Get-Date -Format "yyyyMMdd_HHmmss" } else { $RunId.Trim() }
if ($batchTs -notmatch '^\d{8}_\d{6}$') {
    throw "RunId must match yyyyMMdd_HHmmss (example: 20260419_221347)."
}
$summaryRows = @()
$labelRows = @()
$executedScenarios = 0
$skippedScenarios = 0

Write-Host "[2/$totalSteps] Running authenticated performance battery ($Profile profile)..."
Write-Host "Target: ${Protocol}://${TargetHost}:${Port}"
Write-Host "JMeter executable: $resolvedJMeter"

$originalJvmArgs = $env:JVM_ARGS
$originalHeap = $env:HEAP

try {
    Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
    Remove-Item Env:HEAP -ErrorAction SilentlyContinue

foreach ($scenario in $scenarios) {
    $runName = "${batchTs}_$($scenario.Name)"
    $jtlPath = Join-Path $reportsDir "$runName.jtl"
    $htmlPath = Join-Path $reportsDir $runName
    $scenarioLogPath = Join-Path $reportsDir "$runName.jmeter.log"

    if (-not $RerunCompletedScenarios -and (Test-Path $jtlPath) -and ((Get-Item $jtlPath).Length -gt 0)) {
        Write-Host ""
        Write-Host "Skipping scenario $($scenario.Name): existing JTL found ($jtlPath)"
        $summaryRows += Get-JtlSummary -Scenario $scenario.Name -JtlPath $jtlPath
        $labelRows += Get-JtlLabelSummary -Scenario $scenario.Name -JtlPath $jtlPath
        $skippedScenarios++
        continue
    }

    if (Test-Path $jtlPath) {
        Remove-Item $jtlPath -Force
    }
    if (Test-Path $scenarioLogPath) {
        Remove-Item $scenarioLogPath -Force
    }
    if (Test-Path $htmlPath) {
        Remove-Item $htmlPath -Recurse -Force
    }

    Write-Host ""
    Write-Host "Running scenario $($scenario.Name): threads=$($scenario.Threads), ramp_up=$($scenario.RampUp), loops=$($scenario.Loops)"

    $args = @(
        "-n",
        "-t", $testPlan,
        "-l", $jtlPath,
        "-e",
        "-o", $htmlPath,
        "-j", $scenarioLogPath,
        "-Jhost=$TargetHost",
        "-Jprotocol=$Protocol",
        "-Jport=$Port",
        "-Jthreads=$($scenario.Threads)",
        "-Jramp_up=$($scenario.RampUp)",
        "-Jloops=$($scenario.Loops)",
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
        throw "Scenario $($scenario.Name) failed with exit code $LASTEXITCODE. JMeter log: $scenarioLogPath"
    }

    if (-not (Test-Path $jtlPath)) {
        throw "Scenario $($scenario.Name) did not produce JTL output: $jtlPath. Check JMeter log: $scenarioLogPath"
    }

    if ((Get-Item $jtlPath).Length -le 0) {
        throw "Scenario $($scenario.Name) produced an empty JTL output: $jtlPath. Check JMeter log: $scenarioLogPath"
    }

    $summaryRows += Get-JtlSummary -Scenario $scenario.Name -JtlPath $jtlPath
    $labelRows += Get-JtlLabelSummary -Scenario $scenario.Name -JtlPath $jtlPath
    $executedScenarios++
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

Write-Host ""
Write-Host "[3/$totalSteps] Building KPI summary artifacts..."
Write-Host "Scenarios executed: $executedScenarios; scenarios reused: $skippedScenarios"
$summaryCsv = Join-Path $reportReadyDir "summary_${batchTs}.csv"
$labelCsv = Join-Path $reportReadyDir "summary_labels_${batchTs}.csv"
$summaryMd = Join-Path $reportReadyDir "summary_${batchTs}.md"
$bedrockMd = ""

$summaryRows | Export-Csv -Path $summaryCsv -NoTypeInformation -Encoding UTF8
$labelRows | Export-Csv -Path $labelCsv -NoTypeInformation -Encoding UTF8

$md = @()
$md += "# Auth Performance Battery Summary"
$md += ""
$md += "- Profile: $Profile"
$md += "- Target: ${Protocol}://${TargetHost}:${Port}"
$md += "- Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$md += ""
$md += "## Scenario KPI (overall)"
$md += ""
$md += "| Scenario | Total Requests | Failed | Error % | Avg (ms) | P95 (ms) | P99 (ms) | Min (ms) | Max (ms) | Throughput (req/s) | Duration (s) |"
$md += "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
foreach ($row in $summaryRows) {
    $md += "| $($row.scenario) | $($row.total_requests) | $($row.failed_requests) | $($row.error_rate_pct) | $($row.avg_latency_ms) | $($row.p95_latency_ms) | $($row.p99_latency_ms) | $($row.min_latency_ms) | $($row.max_latency_ms) | $($row.throughput_rps) | $($row.duration_sec) |"
}
$md += ""
$md += "Detailed per-endpoint KPIs are in: $(Split-Path -Leaf $labelCsv)"

Set-Content -Path $summaryMd -Value $md -Encoding UTF8

if ($AnalyzeWithBedrock) {
    Write-Host "[4/$totalSteps] Running Bedrock analysis..."
    $bedrockMd = Join-Path $reportReadyDir "bedrock_analysis_${batchTs}.md"

    try {
        Invoke-BedrockSummaryAnalysis `
            -SummaryCsvPath $summaryCsv `
            -LabelCsvPath $labelCsv `
            -OutputMarkdownPath $bedrockMd `
            -ModelId $BedrockModelId `
            -Region $BedrockRegion `
            -Target "${Protocol}://${TargetHost}:${Port}" `
            -ProfileName $Profile
    }
    catch {
        if ($FailIfBedrockAnalysisFails) {
            throw
        }

        Write-Warning "Bedrock analysis skipped due to error: $($_.Exception.Message)"
        $bedrockMd = ""
    }
}

Write-Host "Done."
Write-Host "Scenario summary CSV: $summaryCsv"
Write-Host "Per-label summary CSV: $labelCsv"
Write-Host "Markdown summary: $summaryMd"
Write-Host "HTML dashboards: $reportsDir"
Write-Host "Report-ready summaries: $reportReadyDir"
if (-not [string]::IsNullOrWhiteSpace($bedrockMd)) {
    Write-Host "Bedrock analysis markdown: $bedrockMd"
}

exit 0
