param(
    [string]$Base = "https://k2p-bkmind-learning-platform.com",
    [string]$UserPassword = "LoadTest@2026!",
    [string]$PdfPath = "",
    [int[]]$CoarseLevels = @(10, 20, 30, 40, 50),
    [int]$MaxThreads = 50,
    [int]$RampSecondsPerUser = 20,
    [double]$MaxUploadErrPct = 0,
    [double]$MaxProcessErrPct = 0,
    [double]$MaxIndexErrPct = 0,
    [switch]$RequireP95Gate,
    [double]$MaxProcessP95Ms = 30000,
    [double]$MaxIndexP95Ms = 30000,
    [switch]$SkipPreflight,
    [int]$PreflightMaxAttempts = 20,
    [int]$PreflightIntervalSeconds = 20,
    [int]$RequestTimeoutSeconds = 180
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if ([string]::IsNullOrWhiteSpace($PdfPath)) {
    throw "PdfPath is required."
}

if (-not (Test-Path $PdfPath)) {
    throw "PDF not found: $PdfPath"
}

$runner = Join-Path $scriptDir "run_main_apis_focus_tests.ps1"
if (-not (Test-Path $runner)) {
    throw "Runner script not found: $runner"
}

$baseUrl = $Base.TrimEnd("/")
$batch = Get-Date -Format "yyyyMMddHHmmssfff"
$tmpDir = Join-Path $scriptDir "reports\pipeline-binary-pdf-standard-multiuser-$batch"
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

$tested = @{}

function Limit-Text {
    param(
        [AllowNull()]
        [string]$Text,
        [int]$MaxLength = 500
    )

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return ""
    }

    if ($Text.Length -le $MaxLength) {
        return $Text
    }

    return $Text.Substring(0, $MaxLength)
}

function Get-DetailFromBody {
    param(
        [AllowNull()]
        [string]$Body
    )

    if ([string]::IsNullOrWhiteSpace($Body)) {
        return ""
    }

    try {
        $obj = $Body | ConvertFrom-Json -ErrorAction Stop
        if ($obj.detail) {
            return (Limit-Text -Text ([string]$obj.detail) -MaxLength 500)
        }
        if ($obj.message) {
            return (Limit-Text -Text ([string]$obj.message) -MaxLength 500)
        }
    }
    catch {
        # Return raw body below.
    }

    return (Limit-Text -Text $Body -MaxLength 500)
}

function Invoke-MultipartUpload {
    param(
        [string]$Uri,
        [hashtable]$Headers,
        [string]$FilePath,
        [int]$TimeoutSec = 180
    )

    try {
        Add-Type -AssemblyName System.Net.Http -ErrorAction SilentlyContinue | Out-Null
    }
    catch {
        # Best effort; type construction below will surface an actionable error if missing.
    }

    $client = New-Object System.Net.Http.HttpClient
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSec)
    $multipart = $null
    $stream = $null
    $fileContent = $null

    try {
        foreach ($k in $Headers.Keys) {
            [void]$client.DefaultRequestHeaders.TryAddWithoutValidation([string]$k, [string]$Headers[$k])
        }

        $multipart = New-Object System.Net.Http.MultipartFormDataContent
        $stream = [System.IO.File]::OpenRead($FilePath)
        $fileContent = New-Object System.Net.Http.StreamContent($stream)
        $fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/pdf")
        $multipart.Add($fileContent, "files", [System.IO.Path]::GetFileName($FilePath))

        $resp = $client.PostAsync($Uri, $multipart).GetAwaiter().GetResult()
        $body = $resp.Content.ReadAsStringAsync().GetAwaiter().GetResult()

        return [pscustomobject]@{
            status_code = [int]$resp.StatusCode
            body = $body
        }
    }
    finally {
        if ($fileContent) { $fileContent.Dispose() }
        if ($stream) { $stream.Dispose() }
        if ($multipart) { $multipart.Dispose() }
        $client.Dispose()
    }
}

function Get-WebErrorInfo {
    param([System.Management.Automation.ErrorRecord]$ErrorRecord)

    $status = 0
    $body = ""
    $detail = ""

    try {
        if ($ErrorRecord.Exception -and $ErrorRecord.Exception.Response) {
            $resp = $ErrorRecord.Exception.Response
            if ($resp.StatusCode) {
                try {
                    $status = [int]$resp.StatusCode
                }
                catch {
                    $status = [int]$resp.StatusCode.value__
                }
            }

            $stream = $resp.GetResponseStream()
            if ($stream) {
                $reader = New-Object System.IO.StreamReader($stream)
                $body = $reader.ReadToEnd()
            }
        }
    }
    catch {
        # Fall through and keep best-effort details below.
    }

    if ([string]::IsNullOrWhiteSpace($body) -and $ErrorRecord.ErrorDetails -and $ErrorRecord.ErrorDetails.Message) {
        $body = [string]$ErrorRecord.ErrorDetails.Message
    }

    if ([string]::IsNullOrWhiteSpace($body)) {
        $body = [string]$ErrorRecord.Exception.Message
    }

    try {
        $obj = $body | ConvertFrom-Json -ErrorAction Stop
        if ($obj.detail) {
            $detail = [string]$obj.detail
        }
        elseif ($obj.message) {
            $detail = [string]$obj.message
        }
        else {
            $detail = [string]$body
        }
    }
    catch {
        $detail = [string]$body
    }

    return [pscustomobject]@{
        status = $status
        detail = (Limit-Text -Text $detail -MaxLength 500)
        body = (Limit-Text -Text $body -MaxLength 1000)
    }
}

function New-FreshUsersCsv {
    param(
        [int]$Threads,
        [string]$RunTag,
        [string]$CsvPath
    )

    $rows = @()
    for ($i = 1; $i -le $Threads; $i++) {
        $idx = "{0:D2}" -f $i
        $email = "pipeline_${RunTag}_u${idx}@local.dev"
        $username = "pipeline_${RunTag}_u${idx}"
        $display = "Pipeline User ${RunTag} ${idx}"

        $regBody = @{
            email = $email
            password = $UserPassword
            username = $username
            displayName = $display
            role = "student"
        } | ConvertTo-Json

        try {
            $reg = Invoke-WebRequest -Uri "$baseUrl/api/auth/register-local" -Method Post -ContentType "application/json" -Body $regBody -UseBasicParsing -TimeoutSec 60
            Write-Host "REGISTER_STATUS=$($reg.StatusCode) EMAIL=$email"
        }
        catch {
            $status = $null
            if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
                $status = [int]$_.Exception.Response.StatusCode.value__
            }
            if ($status -ne 409) {
                throw
            }
            Write-Host "REGISTER_STATUS=409 EMAIL=$email"
        }

        $rows += [pscustomobject]@{
            login_email = $email
            login_password = $UserPassword
        }
    }

    $rows | Export-Csv -Path $CsvPath -NoTypeInformation -Encoding UTF8
}

function Invoke-ApiPipelineProbe {
    param(
        [string]$Email,
        [string]$Password,
        [int]$TimeoutSec = 180
    )

    $result = [ordered]@{
        user_email = $Email
        login_status = 0
        login_detail = ""
        upload_status = 0
        upload_detail = ""
        process_status = 0
        process_detail = ""
        index_status = 0
        index_detail = ""
        pass = $false
    }

    $loginBody = @{ email = $Email; password = $Password } | ConvertTo-Json -Compress
    try {
        $login = Invoke-RestMethod -Uri "$baseUrl/api/auth/login-local" -Method Post -ContentType "application/json" -Body $loginBody -TimeoutSec $TimeoutSec
        $result.login_status = 200
    }
    catch {
        $info = Get-WebErrorInfo -ErrorRecord $_
        $result.login_status = [int]$info.status
        $result.login_detail = [string]$info.detail
        $result.upload_detail = "skipped_due_login_failure"
        $result.process_detail = "skipped_due_login_failure"
        $result.index_detail = "skipped_due_login_failure"
        return [pscustomobject]$result
    }

    $token = [string]$login.access_token
    $uid = [string]$login.user.uid
    $authHeaders = @{ Authorization = "Bearer $token"; "X-User-Id" = $uid }

    try {
        $uploadResp = Invoke-MultipartUpload -Uri "$baseUrl/api/upload" -Headers $authHeaders -FilePath $PdfPath -TimeoutSec $TimeoutSec
        $result.upload_status = [int]$uploadResp.status_code
        if ($result.upload_status -ne 200) {
            $result.upload_detail = (Get-DetailFromBody -Body ([string]$uploadResp.body))
            $result.process_detail = "skipped_due_upload_failure"
            $result.index_detail = "skipped_due_upload_failure"
            return [pscustomobject]$result
        }
    }
    catch {
        $info = Get-WebErrorInfo -ErrorRecord $_
        $result.upload_status = [int]$info.status
        $result.upload_detail = [string]$info.detail
        $result.process_detail = "skipped_due_upload_failure"
        $result.index_detail = "skipped_due_upload_failure"
        return [pscustomobject]$result
    }

    $processBody = @{ selected_paths = @(); mode = "standard" } | ConvertTo-Json -Compress
    try {
        $processResp = Invoke-WebRequest -Uri "$baseUrl/api/process?force=false" -Method Post -Headers $authHeaders -ContentType "application/json" -Body $processBody -TimeoutSec $TimeoutSec
        $result.process_status = [int]$processResp.StatusCode
    }
    catch {
        $info = Get-WebErrorInfo -ErrorRecord $_
        $result.process_status = [int]$info.status
        $result.process_detail = [string]$info.detail
    }

    $indexBody = @{ selected_paths = @(); selected_names = @(); mode = "standard" } | ConvertTo-Json -Compress
    try {
        $indexResp = Invoke-WebRequest -Uri "$baseUrl/api/index?force=false" -Method Post -Headers $authHeaders -ContentType "application/json" -Body $indexBody -TimeoutSec $TimeoutSec
        $result.index_status = [int]$indexResp.StatusCode
    }
    catch {
        $info = Get-WebErrorInfo -ErrorRecord $_
        $result.index_status = [int]$info.status
        $result.index_detail = [string]$info.detail
    }

    $result.pass = ($result.upload_status -eq 200) -and ($result.process_status -eq 200) -and ($result.index_status -eq 200)
    return [pscustomobject]$result
}

function Invoke-EndpointPreflight {
    param(
        [int]$MaxAttempts,
        [int]$IntervalSeconds,
        [int]$TimeoutSec
    )

    $history = @()
    $attempt = 0

    while ($true) {
        $attempt += 1
        $runTag = "PREFLIGHT_A${attempt}_$(Get-Date -Format yyyyMMddHHmmssfff)"
        $usersCsv = Join-Path $tmpDir "users_$runTag.csv"
        New-FreshUsersCsv -Threads 1 -RunTag $runTag -CsvPath $usersCsv

        $probeUser = Import-Csv $usersCsv | Select-Object -First 1
        $probe = Invoke-ApiPipelineProbe -Email $probeUser.login_email -Password $probeUser.login_password -TimeoutSec $TimeoutSec

        $row = [pscustomobject]@{
            attempt = $attempt
            pass = [bool]$probe.pass
            user_email = [string]$probe.user_email
            login_status = [int]$probe.login_status
            login_detail = (Limit-Text -Text ([string]$probe.login_detail) -MaxLength 500)
            upload_status = [int]$probe.upload_status
            upload_detail = (Limit-Text -Text ([string]$probe.upload_detail) -MaxLength 500)
            process_status = [int]$probe.process_status
            process_detail = (Limit-Text -Text ([string]$probe.process_detail) -MaxLength 500)
            index_status = [int]$probe.index_status
            index_detail = (Limit-Text -Text ([string]$probe.index_detail) -MaxLength 500)
        }

        $history += $row
        Write-Host "PREFLIGHT attempt=$attempt pass=$($row.pass) upload=$($row.upload_status) process=$($row.process_status) index=$($row.index_status)"

        if ([bool]$row.pass) {
            break
        }

        if ($MaxAttempts -gt 0 -and $attempt -ge $MaxAttempts) {
            break
        }

        if ($IntervalSeconds -gt 0) {
            Start-Sleep -Seconds $IntervalSeconds
        }
    }

    $preflightCsv = Join-Path $scriptDir "report-ready\pipeline_endpoint_preflight_$batch.csv"
    $history | Export-Csv -Path $preflightCsv -NoTypeInformation -Encoding UTF8

    $last = $history[-1]
    return [pscustomobject]@{
        pass = [bool]$last.pass
        attempts = $attempt
        csv = $preflightCsv
        last = $last
    }
}

function Invoke-LevelTest {
    param([int]$Threads)

    $key = $Threads.ToString()
    if ($tested.ContainsKey($key)) {
        return $tested[$key]
    }

    $runTag = "MU_L${Threads}_$(Get-Date -Format yyyyMMddHHmmssfff)"
    $usersCsv = Join-Path $tmpDir "users_$runTag.csv"
    New-FreshUsersCsv -Threads $Threads -RunTag $runTag -CsvPath $usersCsv

    Remove-Item Env:JVM_ARGS -ErrorAction SilentlyContinue
    Remove-Item Env:HEAP -ErrorAction SilentlyContinue

    $ec = 1
    $failReason = @()

    try {
        $null = & $runner `
            -Threads $Threads `
            -RampUp ([Math]::Max(1, $Threads * $RampSecondsPerUser)) `
            -Loops 1 `
            -SkipAccountSetup `
            -RunSearchApis:$false `
            -RunPipelineApis `
            -RunUploadApi `
            -RunProcessApi `
            -RunIndexApi `
            -UsersShareMode "shareMode.group" `
            -PipelineAllThreads `
            -UsersCsvPath $usersCsv `
            -UploadFilePath $PdfPath `
            -UploadMimeType "application/pdf" `
            -ProcessMode "standard" `
            -IndexMode "standard"

        if ($null -eq $LASTEXITCODE) {
            $ec = 0
        }
        else {
            $ec = [int]$LASTEXITCODE
        }
    }
    catch {
        $ec = 1
        $failReason += "runner_exception"
        Write-Warning "Runner exception at threads=${Threads}: $($_.Exception.Message)"
    }

    $labels = Get-ChildItem (Join-Path $scriptDir "report-ready\main_apis_labels_*.csv") -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    $uploadErr = 100.0
    $processErr = 100.0
    $indexErr = 100.0
    $uploadP95 = 0.0
    $processP95 = 0.0
    $indexP95 = 0.0
    $labelsFile = ""
    $diagUserEmail = ""
    $diagLoginStatus = 0
    $diagLoginDetail = ""
    $diagUploadStatus = 0
    $diagUploadDetail = ""
    $diagProcessStatus = 0
    $diagProcessDetail = ""
    $diagIndexStatus = 0
    $diagIndexDetail = ""

    if ($labels) {
        $labelsFile = $labels.Name
        $table = Import-Csv $labels.FullName

        $upload = $table | Where-Object label -eq "POST /api/upload (core)" | Select-Object -First 1
        $process = $table | Where-Object label -eq "POST /api/process (core)" | Select-Object -First 1
        $index = $table | Where-Object label -eq "POST /api/index (core)" | Select-Object -First 1

        if ($upload) {
            $uploadErr = [double]$upload.error_rate_pct
            $uploadP95 = [double]$upload.p95_latency_ms
        }
        else {
            $failReason += "missing_upload_label"
        }

        if ($process) {
            $processErr = [double]$process.error_rate_pct
            $processP95 = [double]$process.p95_latency_ms
        }
        else {
            $failReason += "missing_process_label"
        }

        if ($index) {
            $indexErr = [double]$index.error_rate_pct
            $indexP95 = [double]$index.p95_latency_ms
        }
        else {
            $failReason += "missing_index_label"
        }
    }
    else {
        $failReason += "missing_labels_file"
    }

    $isPass = ($ec -eq 0) -and ($uploadErr -le $MaxUploadErrPct) -and ($processErr -le $MaxProcessErrPct) -and ($indexErr -le $MaxIndexErrPct)

    if ($RequireP95Gate) {
        $isPass = $isPass -and ($processP95 -le $MaxProcessP95Ms) -and ($indexP95 -le $MaxIndexP95Ms)
        if (-not ($processP95 -le $MaxProcessP95Ms)) {
            $failReason += "process_p95_exceeded"
        }
        if (-not ($indexP95 -le $MaxIndexP95Ms)) {
            $failReason += "index_p95_exceeded"
        }
    }

    if ($ec -ne 0) { $failReason += "runner_exit_nonzero" }
    if ($uploadErr -gt $MaxUploadErrPct) { $failReason += "upload_error_exceeded" }
    if ($processErr -gt $MaxProcessErrPct) { $failReason += "process_error_exceeded" }
    if ($indexErr -gt $MaxIndexErrPct) { $failReason += "index_error_exceeded" }

    if (-not $isPass) {
        try {
            $probeUser = Import-Csv $usersCsv | Select-Object -First 1
            if ($probeUser) {
                $diagUserEmail = [string]$probeUser.login_email
                $diag = Invoke-ApiPipelineProbe -Email $diagUserEmail -Password ([string]$probeUser.login_password) -TimeoutSec $RequestTimeoutSeconds
                $diagLoginStatus = [int]$diag.login_status
                $diagLoginDetail = (Limit-Text -Text ([string]$diag.login_detail) -MaxLength 500)
                $diagUploadStatus = [int]$diag.upload_status
                $diagUploadDetail = (Limit-Text -Text ([string]$diag.upload_detail) -MaxLength 500)
                $diagProcessStatus = [int]$diag.process_status
                $diagProcessDetail = (Limit-Text -Text ([string]$diag.process_detail) -MaxLength 500)
                $diagIndexStatus = [int]$diag.index_status
                $diagIndexDetail = (Limit-Text -Text ([string]$diag.index_detail) -MaxLength 500)
            }
        }
        catch {
            $failReason += "diag_probe_exception"
        }
    }

    $row = [pscustomobject]@{
        threads = $Threads
        pass = $isPass
        fail_reason = (($failReason | Select-Object -Unique) -join ",")
        exit_code = $ec
        labels_file = $labelsFile
        upload_err_pct = [math]::Round($uploadErr, 4)
        upload_p95_ms = [math]::Round($uploadP95, 2)
        process_err_pct = [math]::Round($processErr, 4)
        process_p95_ms = [math]::Round($processP95, 2)
        index_err_pct = [math]::Round($indexErr, 4)
        index_p95_ms = [math]::Round($indexP95, 2)
        diag_user_email = $diagUserEmail
        diag_login_status = $diagLoginStatus
        diag_login_detail = $diagLoginDetail
        diag_upload_status = $diagUploadStatus
        diag_upload_detail = $diagUploadDetail
        diag_process_status = $diagProcessStatus
        diag_process_detail = $diagProcessDetail
        diag_index_status = $diagIndexStatus
        diag_index_detail = $diagIndexDetail
    }

    $tested[$key] = $row
    Write-Host "TEST threads=$Threads pass=$isPass upload_err=$($row.upload_err_pct) process_err=$($row.process_err_pct) index_err=$($row.index_err_pct) users_mode=shareMode.group"
    return $row
}

function Resolve-LevelResult {
    param([object]$RawResult)

    $items = @($RawResult)
    $candidates = @(
        $items | Where-Object {
            $_ -and $_.PSObject -and ($_.PSObject.Properties.Name -contains "pass")
        }
    )

    if ($candidates.Count -gt 0) {
        return $candidates[-1]
    }

    if ($items.Count -gt 0) {
        return $items[-1]
    }

    return $null
}

Write-Host "Running multi-user pipeline test (standard mode, PDF)"
Write-Host "Users assignment mode: shareMode.group (shared CSV cursor -> distinct rows per thread when Loops=1 and rows>=threads)"

if (-not $SkipPreflight) {
    Write-Host "Running endpoint preflight before binary search..."
    $preflight = Invoke-EndpointPreflight -MaxAttempts $PreflightMaxAttempts -IntervalSeconds $PreflightIntervalSeconds -TimeoutSec $RequestTimeoutSeconds
    Write-Host "PREFLIGHT_CSV=$($preflight.csv)"

    if (-not [bool]$preflight.pass) {
        $last = $preflight.last
        throw (
            "Preflight failed after $($preflight.attempts) attempt(s). " +
            "process_status=$($last.process_status), process_detail=$($last.process_detail), " +
            "index_status=$($last.index_status), index_detail=$($last.index_detail). " +
            "See: $($preflight.csv)"
        )
    }

    Write-Host "Preflight passed after $($preflight.attempts) attempt(s). Continue to binary search..."
}

$lastPass = 0
$firstFail = $null

foreach ($lv in $CoarseLevels) {
    if ($lv -gt $MaxThreads) {
        continue
    }
    $rRaw = Invoke-LevelTest -Threads $lv
    $r = Resolve-LevelResult -RawResult $rRaw
    if (-not $r -or -not ($r.PSObject.Properties.Name -contains "pass")) {
        $rawTypes = (@($rRaw) | ForEach-Object { if ($_ -eq $null) { "<null>" } else { $_.GetType().FullName } }) -join ", "
        throw "Invalid level result at threads=$lv. Expected object with property 'pass'. Raw types: $rawTypes"
    }

    if ([bool]$r.pass) {
        $lastPass = $lv
    }
    else {
        $firstFail = $lv
        break
    }
}

if ($null -eq $firstFail) {
    $bestThreads = $lastPass
}
else {
    $lo = $lastPass
    $hi = $firstFail

    while (($hi - $lo) -gt 1) {
        $mid = [int][math]::Floor(($lo + $hi) / 2)
        if ($mid -lt 1) {
            $mid = 1
        }

        $rRaw = Invoke-LevelTest -Threads $mid
        $r = Resolve-LevelResult -RawResult $rRaw
        if (-not $r -or -not ($r.PSObject.Properties.Name -contains "pass")) {
            $rawTypes = (@($rRaw) | ForEach-Object { if ($_ -eq $null) { "<null>" } else { $_.GetType().FullName } }) -join ", "
            throw "Invalid level result at threads=$mid. Expected object with property 'pass'. Raw types: $rawTypes"
        }

        if ([bool]$r.pass) {
            $lo = $mid
        }
        else {
            $hi = $mid
        }
    }

    $bestThreads = $lo
}

$rows = $tested.GetEnumerator() | ForEach-Object { $_.Value } | Sort-Object { [int]$_.threads }
$outCsv = Join-Path $scriptDir "report-ready\pipeline_concurrency_pdf_standard_multiuser_binary_$batch.csv"
$rows | Export-Csv -Path $outCsv -NoTypeInformation -Encoding UTF8

$rows | Format-Table -AutoSize
Write-Host "BEST_THREADS=$bestThreads"
Write-Host "RESULTS_CSV=$outCsv"
