param(
    [string]$APIHost = "k2p-bkmind-learning-platform.com",
    [int]$Port = 443,
    [string]$Protocol = "https",
    [string]$UsersCSV = "data/users.csv",
    [string]$UploadFile = "data/Text_mining_by_using_Python2025_5pages.pdf",
    [string]$OutputMapping = "data/user_file_mapping.csv"
)

$ErrorActionPreference = "Stop"
$BaseUrl = "$Protocol`://$APIHost`:$Port"

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "BK-MInD - Setup Phase 1: Upload Files for 50 Users" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# Read users
$users = @()
$csv = Import-Csv $UsersCSV
$csv | ForEach-Object { $users += $_ }

Write-Host "[INFO] Loaded $($users.Count) users from $UsersCSV"

# Create mapping file header
$mapping = @()
$mapping += "email,file_path"

$successCount = 0
$errorCount = 0

# Upload file for each user
for ($i = 0; $i -lt $users.Count; $i++) {
    $user = $users[$i]
    $email = $user.email
    $password = $user.password
    $userNum = $i + 1

    try {
        Write-Host "[$userNum/$($users.Count)] Processing user: $email" -ForegroundColor Yellow

        # Step 1: Login
        $loginUrl = "$BaseUrl/api/auth/login-local"
        $loginBody = @{
            email = $email
            password = $password
        } | ConvertTo-Json

        $loginResponse = Invoke-WebRequest -Uri $loginUrl `
            -Method POST `
            -Headers @{ "Content-Type" = "application/json" } `
            -Body $loginBody `
            -UseBasicParsing

        $loginData = $loginResponse.Content | ConvertFrom-Json
        $token = $loginData.access_token

        Write-Host "  ✓ Authenticated" -ForegroundColor Green

        # Step 2: Upload file using simple multipart
        $uploadUrl = "$BaseUrl/api/upload"
        $fileName = "Text_mining_user_$userNum.pdf"

        $fileInfo = Get-Item $UploadFile
        $uploadResponse = Invoke-WebRequest -Uri $uploadUrl `
            -Method POST `
            -Headers @{ "Authorization" = "Bearer $token" } `
            -Form @{ files = $fileInfo } `
            -UseBasicParsing

        $uploadData = $uploadResponse.Content | ConvertFrom-Json
        $filePath = $uploadData.data[0].path

        Write-Host "  ✓ Uploaded: $fileName -> $filePath" -ForegroundColor Green

        # Store mapping
        $mapping += "$email,$filePath"
        $successCount++

    } catch {
        Write-Host "  ✗ Error: $($_.Exception.Message)" -ForegroundColor Red
        $errorCount++
    }
}

# Save mapping
$mapping | Out-File -FilePath $OutputMapping -Encoding UTF8
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "SETUP COMPLETE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "✓ Successful uploads: $successCount" -ForegroundColor Green
Write-Host "✗ Failed uploads: $errorCount" -ForegroundColor $(if ($errorCount -eq 0) { "Green" } else { "Red" })
Write-Host "✓ Mapping saved to: $OutputMapping" -ForegroundColor Green
Write-Host ""
Write-Host "Mapping sample (first 5):"
Get-Content $OutputMapping | Select-Object -First 6

Write-Host ""
Write-Host "Next: Run the test with:"
Write-Host "jmeter -n -t 05_process_mapped.jmx -Jhost=k2p-bkmind-learning-platform.com -Jport=443 -Jthreads=50 -Jramp_up=10 -Jduration=90 -l results/process_mapped_50threads.jtl" -ForegroundColor Cyan
