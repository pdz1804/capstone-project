# BK-MInD Capacity Finder - Quick Test Runner
# Tests all APIs to find concurrent user capacity
# Usage: .\run_capacity_finder_fixed.ps1 -APIs all -ApiHost "host" -Port 443

param(
    [Parameter(Mandatory=$false)][string]$APIs = "all",
    [Parameter(Mandatory=$false)][string]$ApiHost = "k2p-bkmind-learning-platform.com",
    [Parameter(Mandatory=$false)][int]$Port = 443,
    [Parameter(Mandatory=$false)][string]$Protocol = "https",
    [Parameter(Mandatory=$false)][string]$JmeterPath = "jmeter.bat",
    [Parameter(Mandatory=$false)][string]$OutputDir = "results"
)

# Configuration - Default values (can be overridden per endpoint type)
$ThreadLevels = @(5, 10, 20, 30, 40, 50)
$RampUpSeconds = 5
$DurationSeconds = 15

# Extended times for I/O-heavy endpoints (upload, process, index, search)
$RampUpSecondsIO = 10
$DurationSecondsIO = 90

$TotalTimePerLevel = $RampUpSeconds + $DurationSeconds

# Output functions
function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host ("=" * 80) -ForegroundColor Cyan
    Write-Host $Text -ForegroundColor Cyan
    Write-Host ("=" * 80) -ForegroundColor Cyan
}

function Write-InfoMsg {
    param([string]$Text)
    Write-Host "[INFO] $Text" -ForegroundColor Blue
}

function Write-SuccessMsg {
    param([string]$Text)
    Write-Host "[OK] $Text" -ForegroundColor Green
}

function Write-ErrorMsg {
    param([string]$Text)
    Write-Host "[ERROR] $Text" -ForegroundColor Red
}

# API configurations
$ApiTests = @{
    "01_auth_login" = @{ Name = "POST /api/auth/login-local"; Type = "auth"; Requires = "users.csv" }
    "02_user_me" = @{ Name = "GET /api/users/me"; Type = "get"; Requires = "token" }
    "03_stats" = @{ Name = "GET /api/processing-stats"; Type = "get"; Requires = "token" }
    "04_upload" = @{ Name = "POST /api/upload"; Type = "upload"; Requires = "test_file" }
    "05_process" = @{ Name = "POST /api/process"; Type = "post"; Requires = "file_ids.csv" }
    "06_index" = @{ Name = "POST /api/index"; Type = "post"; Requires = "file_ids.csv" }
    "07_search_retrieval" = @{ Name = "POST /api/search"; Type = "post"; Requires = "search_queries.csv" }
    "08_chat_stream" = @{ Name = "POST /api/chat/stream"; Type = "post"; Requires = "chat_messages.csv" }
    "09_insights_summary" = @{ Name = "POST /api/insights/summary"; Type = "post"; Requires = "file_ids.csv" }
    "10_insights_roadmap" = @{ Name = "POST /api/insights/learning-roadmap"; Type = "post"; Requires = "file_ids.csv" }
    "11_insights_mcq" = @{ Name = "POST /api/insights/mcq"; Type = "post"; Requires = "file_ids.csv" }
}

function Parse-JMeterResults {
    param([string]$JtlFile)
    
    if (-not (Test-Path $JtlFile)) {
        return @{ Success = 0; Failed = 0; Total = 0; AvgTime = 0; P95 = 0; P99 = 0; ErrorRate = 100 }
    }
    
    $data = @()
    try {
        $data = Import-Csv -Path $JtlFile -ErrorAction Stop
    } catch {
        Write-ErrorMsg "Failed to parse JTL file: $JtlFile"
        return @{ Success = 0; Failed = 0; Total = 0; AvgTime = 0; P95 = 0; P99 = 0; ErrorRate = 100 }
    }
    
    $successCount = ($data | Where-Object { $_.success -eq 'true' }).Count
    $failedCount = ($data | Where-Object { $_.success -eq 'false' }).Count
    $totalRequests = $data.Count
    
    if ($totalRequests -eq 0) {
        return @{ Success = 0; Failed = 0; Total = 0; AvgTime = 0; P95 = 0; P99 = 0; ErrorRate = 100 }
    }
    
    $responseTimes = @()
    foreach ($row in $data) {
        if ($null -ne $row.elapsed -and $row.elapsed -match '^\d+$') {
            $responseTimes += [int]$row.elapsed
        }
    }
    
    $responseTimes = $responseTimes | Sort-Object
    $avgTime = if ($responseTimes.Count -gt 0) { ($responseTimes | Measure-Object -Average).Average } else { 0 }
    
    $p95Index = [Math]::Floor($responseTimes.Count * 0.95)
    $p99Index = [Math]::Floor($responseTimes.Count * 0.99)
    
    $p95 = if ($p95Index -ge 0 -and $p95Index -lt $responseTimes.Count) { $responseTimes[$p95Index] } else { 0 }
    $p99 = if ($p99Index -ge 0 -and $p99Index -lt $responseTimes.Count) { $responseTimes[$p99Index] } else { 0 }
    
    return @{
        Success = $successCount
        Failed = $failedCount
        Total = $totalRequests
        AvgTime = [math]::Round($avgTime, 2)
        P95 = $p95
        P99 = $p99
        ErrorRate = if ($totalRequests -gt 0) { [math]::Round(($failedCount / $totalRequests) * 100, 2) } else { 100 }
    }
}

function Run-ApiTest {
    param(
        [string]$ApiName,
        [string]$JmxFile,
        [int]$Threads,
        [int]$RampUp,
        [int]$Duration
    )
    
    $jtlFile = "$OutputDir\${ApiName}_${Threads}threads_$(Get-Date -Format yyyyMMdd_HHmmss).jtl"
    
    Write-InfoMsg "Running: $ApiName | Threads: $Threads | Ramp-up: ${RampUp}s | Duration: ${Duration}s"
    
    try {
        $jmeterArgs = @(
            "-n"
            "-t", $JmxFile
            "-l", $jtlFile
            "-Jprotocol=$Protocol"
            "-Jhost=$ApiHost"
            "-Jport=$Port"
            "-Jthreads=$Threads"
            "-Jramp_up=$RampUp"
            "-Jduration=$Duration"
        )
        
        $process = Start-Process -FilePath $JmeterPath -ArgumentList $jmeterArgs -NoNewWindow -Wait -PassThru
        
        if ($process.ExitCode -ne 0) {
            Write-ErrorMsg "JMeter execution failed with exit code $($process.ExitCode)"
            return @{ Threads = $Threads; Total = 0; Success = 0; Failed = 0; ErrorRate = 100; AvgTime = 0; P95 = 0; P99 = 0 }
        }
        
        $results = Parse-JMeterResults -JtlFile $jtlFile
        $results.Threads = $Threads
        
        return $results
    } catch {
        Write-ErrorMsg "Exception during test: $($_.Exception.Message)"
        return @{ Threads = $Threads; Total = 0; Success = 0; Failed = 0; ErrorRate = 100; AvgTime = 0; P95 = 0; P99 = 0 }
    }
}

# Main execution
Write-Header "BK-MInD API Capacity Finder"

Write-InfoMsg "Configuration:"
Write-InfoMsg "  API Host: $ApiHost"
Write-InfoMsg "  Port: $Port"
Write-InfoMsg "  Protocol: $Protocol"
Write-InfoMsg "  Thread Levels: $($ThreadLevels -join ', ')"
Write-InfoMsg "  Ramp-up: ${RampUpSeconds}s | Duration: ${DurationSeconds}s per level"
Write-InfoMsg "  Estimated time per API: ~$(($ThreadLevels.Count * $TotalTimePerLevel) / 60) minutes"

# Create output directory
if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# Get APIs to test
$apisToTest = @()
if ($APIs -eq "all") {
    $apisToTest = $ApiTests.Keys | Sort-Object
} else {
    $apisToTest = @($APIs)
}

Write-InfoMsg "Testing APIs: $($apisToTest -join ', ')"

$allResults = @()

foreach ($apiKey in $apisToTest) {
    if (-not $ApiTests.ContainsKey($apiKey)) {
        Write-ErrorMsg "API not found: $apiKey"
        continue
    }
    
    $api = $ApiTests[$apiKey]
    $jmxFile = "./${apiKey}.jmx"
    
    if (-not (Test-Path $jmxFile)) {
        Write-ErrorMsg "JMX file not found: $jmxFile"
        continue
    }
    
    Write-Header "Testing: $($api.Name)"

    # Use extended times for I/O-heavy endpoints
    $useExtendedTimes = $api.Type -in @("upload", "post") -and $apiKey -in @("04_upload", "05_process", "06_index", "07_search_retrieval")
    $rampUp = if ($useExtendedTimes) { $RampUpSecondsIO } else { $RampUpSeconds }
    $duration = if ($useExtendedTimes) { $DurationSecondsIO } else { $DurationSeconds }

    if ($useExtendedTimes) {
        Write-InfoMsg "Using extended times for I/O-heavy endpoint: Ramp-up=${rampUp}s, Duration=${duration}s"
    }

    $apiResults = @()
    $maxCapacity = 0

    foreach ($threads in $ThreadLevels) {
        $result = Run-ApiTest -ApiName $apiKey -JmxFile $jmxFile -Threads $threads -RampUp $rampUp -Duration $duration
        $apiResults += $result
        
        Write-InfoMsg "  Result: Total=$($result.Total) | Success=$($result.Success) | Failed=$($result.Failed) | Error=$($result.ErrorRate)%"
        
        if ($result.ErrorRate -le 5) {
            $maxCapacity = $threads
        } else {
            Write-InfoMsg "  Breaking at $threads threads (error rate exceeded 5%)"
            break
        }
    }
    
    $status = if ($maxCapacity -ge 20) { "PASS" } elseif ($maxCapacity -ge 10) { "WARN" } else { "FAIL" }
    
    $allResults += @{
        ApiKey = $apiKey
        ApiName = $api.Name
        MaxCapacity = $maxCapacity
        Status = $status
        Results = $apiResults
    }
    
    Write-SuccessMsg "Max Concurrent Capacity: $maxCapacity users [$status]"
}

# Generate summary
Write-Header "CAPACITY TEST SUMMARY REPORT"

$table = @()
foreach ($result in $allResults) {
    $table += [PSCustomObject]@{
        "API" = $result.ApiName
        "Max Concurrent" = $result.MaxCapacity
        "Status" = $result.Status
    }
}

$table | Format-Table -AutoSize

# Export to CSV
$csvPath = "$OutputDir\capacity_summary_$(Get-Date -Format yyyyMMdd_HHmmss).csv"
$allResults | ForEach-Object {
    foreach ($levelResult in $_.Results) {
        [PSCustomObject]@{
            API = $_.ApiName
            MaxCapacity = $_.MaxCapacity
            Threads = $levelResult.Threads
            Requests = $levelResult.Total
            Success = $levelResult.Success
            Failed = $levelResult.Failed
            ErrorRate = $levelResult.ErrorRate
            AvgTime = $levelResult.AvgTime
            P95 = $levelResult.P95
            P99 = $levelResult.P99
        }
    }
} | Export-Csv -Path $csvPath -NoTypeInformation

Write-SuccessMsg "Results exported to: $csvPath"
Write-SuccessMsg "Capacity testing complete!"
