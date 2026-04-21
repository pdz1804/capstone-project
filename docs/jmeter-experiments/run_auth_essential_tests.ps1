param(
    [string]$JMeterBin = "jmeter",
    [string]$TargetHost = "k2p-bkmind-learning-platform.com",
    [string]$Protocol = "https",
    [int]$Port = 443,
    [int]$Threads = 10,
    [int]$RampUp = 60,
    [int]$Loops = 1,
    [switch]$EnableMutationApis,
    [string]$UploadFilePath = ""
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

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$testPlan = Join-Path $scriptDir "BKMind_Essential_APIs_Auth.jmx"
$usersCsv = Join-Path $scriptDir "data\users.csv"
$queriesCsv = Join-Path $scriptDir "data\queries.csv"
$reportsDir = Join-Path $scriptDir "reports"

if ([string]::IsNullOrWhiteSpace($UploadFilePath)) {
    $UploadFilePath = Join-Path $scriptDir "data\sample_upload.md"
}

if (-not (Test-Path $testPlan)) {
    throw "Test plan not found: $testPlan"
}
if (-not (Test-Path $usersCsv)) {
    throw "Users CSV not found: $usersCsv"
}
if (-not (Test-Path $queriesCsv)) {
    throw "Queries CSV not found: $queriesCsv"
}

$resolvedJMeter = Resolve-JMeterExecutable -Requested $JMeterBin
$resolvedJMeterCmd = if ($resolvedJMeter -eq "jmeter") { "jmeter" } else { '"' + $resolvedJMeter + '"' }

$originalJvmArgs = $env:JVM_ARGS
$originalHeap = $env:HEAP

$rawUsers = Get-Content -Path $usersCsv -Raw
if ($rawUsers -match "CHANGE_ME") {
    Write-Error "Please update data/users.csv with real credentials before running."
    exit 1
}

New-Item -ItemType Directory -Path $reportsDir -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$jtl = Join-Path $reportsDir "essential_auth_$timestamp.jtl"
$html = Join-Path $reportsDir "essential_auth_$timestamp"
$runLog = Join-Path $reportsDir "essential_auth_$timestamp.jmeter.log"
$runMutationApis = if ($EnableMutationApis) { "true" } else { "false" }

$arguments = @(
    "-n",
    "-t", $testPlan,
    "-l", $jtl,
    "-e",
    "-o", $html,
    "-j", $runLog,
    "-Jhost=$TargetHost",
    "-Jprotocol=$Protocol",
    "-Jport=$Port",
    "-Jthreads=$Threads",
    "-Jramp_up=$RampUp",
    "-Jloops=$Loops",
    "-Jrun_mutation_apis=$runMutationApis",
    "-Jupload_file_path=$UploadFilePath",
    "-Jusers_csv=$usersCsv",
    "-Jqueries_csv=$queriesCsv",
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

Write-Host "Running JMeter authenticated essential API suite..."
Write-Host "Host: ${Protocol}://${TargetHost}:${Port}"
Write-Host "Threads: $Threads | RampUp: $RampUp | Loops: $Loops"
Write-Host "JMeter executable: $resolvedJMeter"
try {
    Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
    Remove-Item Env:HEAP -ErrorAction SilentlyContinue

    $escapedArgs = $arguments | ForEach-Object { '"' + ($_ -replace '"', '\\"') + '"' }
    $cmdLine = "echo.|$resolvedJMeterCmd $($escapedArgs -join ' ')"
    cmd /c $cmdLine

    if ($LASTEXITCODE -ne 0) {
        throw "JMeter run failed with exit code $LASTEXITCODE. JMeter log: $runLog"
    }

    if (-not (Test-Path $jtl)) {
        throw "JMeter run did not produce JTL output: $jtl. Check JMeter log: $runLog"
    }

    if ((Get-Item $jtl).Length -le 0) {
        throw "JMeter run produced an empty JTL output: $jtl. Check JMeter log: $runLog"
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
Write-Host "Done. Artifacts:"
Write-Host "JTL: $jtl"
Write-Host "HTML report: $html\index.html"
Write-Host "JMeter log: $runLog"

exit 0
