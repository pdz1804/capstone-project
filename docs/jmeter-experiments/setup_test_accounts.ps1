param(
    [string]$TargetHost = "k2p-bkmind-learning-platform.com",
    [string]$Protocol = "https",
    [int]$Port = 443,
    [string]$AdminEmail = "admin@local.dev",
    [string]$AdminPassword = "quangphu1804",
    [int]$TestUserCount = 9,
    [string]$TestUserPrefix = "perfuser",
    [string]$TestUserPassword = "LoadTest@2026!",
    [int]$TimeoutSec = 60,
    [string]$OutputCsv = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($OutputCsv)) {
    $OutputCsv = Join-Path $scriptDir "data\users.csv"
}
$baseUrl = "${Protocol}://${TargetHost}:${Port}"

# Bypass SSL certificate validation for self-signed certificates (PowerShell 5.1 compatible)
if (-not ([System.Management.Automation.PSTypeName]'ServerCertificateValidationCallback').Type) {
    $certCallback = @"
        using System;
        using System.Net;
        using System.Net.Security;
        using System.Security.Cryptography.X509Certificates;
        public class ServerCertificateValidationCallback {
            public static void Ignore() {
                if(ServicePointManager.ServerCertificateValidationCallback == null) {
                    ServicePointManager.ServerCertificateValidationCallback += 
                        new RemoteCertificateValidationCallback(ValidateServerCertificate);
                }
            }
            private static bool ValidateServerCertificate(object sender, X509Certificate certificate, X509Chain chain, SslPolicyErrors sslPolicyErrors) {
                return true;
            }
        }
"@
    Add-Type $certCallback
}
[ServerCertificateValidationCallback]::Ignore()

function Invoke-JsonPost {
    param(
        [string]$Url,
        [hashtable]$Payload
    )

    $json = $Payload | ConvertTo-Json -Depth 8 -Compress
    try {
        $resp = Invoke-WebRequest -Uri $Url -Method Post -ContentType "application/json" -Body $json -UseBasicParsing -TimeoutSec $TimeoutSec
        $bodyObj = $null
        if ($resp.Content) {
            try { $bodyObj = $resp.Content | ConvertFrom-Json } catch { $bodyObj = $null }
        }
        return [pscustomobject]@{
            StatusCode = [int]$resp.StatusCode
            Body       = $bodyObj
            Raw        = [string]$resp.Content
        }
    }
    catch {
        $webResp = $_.Exception.Response
        if ($null -eq $webResp) {
            throw
        }

        $statusCode = [int]$webResp.StatusCode
        $raw = ""
        try {
            $stream = $webResp.GetResponseStream()
            if ($stream) {
                $reader = New-Object System.IO.StreamReader($stream)
                $raw = $reader.ReadToEnd()
                $reader.Close()
            }
        }
        catch {
            $raw = ""
        }

        $bodyObj = $null
        if ($raw) {
            try { $bodyObj = $raw | ConvertFrom-Json } catch { $bodyObj = $null }
        }

        return [pscustomobject]@{
            StatusCode = $statusCode
            Body       = $bodyObj
            Raw        = $raw
        }
    }
}

Write-Host "Bootstraping performance-test accounts against: $baseUrl"

$adminLogin = Invoke-JsonPost -Url "$baseUrl/api/auth/login-local" -Payload @{
    email    = $AdminEmail
    password = $AdminPassword
}

if ($adminLogin.StatusCode -ne 200) {
    throw "Admin login failed (HTTP $($adminLogin.StatusCode)). Check -AdminEmail/-AdminPassword before provisioning test users. Response: $($adminLogin.Raw)"
}

$rows = @()
$rows += [pscustomobject]@{
    login_email    = $AdminEmail
    login_password = $AdminPassword
}

$createdCount = 0
$existingCount = 0

for ($i = 1; $i -le $TestUserCount; $i++) {
    $suffix = "{0:D2}" -f $i
    $email = "$TestUserPrefix$suffix@local.dev"
    $username = "$TestUserPrefix$suffix"
    $displayName = "Performance User $suffix"

    $registerResp = Invoke-JsonPost -Url "$baseUrl/api/auth/register-local" -Payload @{
        email       = $email
        password    = $TestUserPassword
        username    = $username
        displayName = $displayName
        role        = "student"
    }

    if ($registerResp.StatusCode -eq 200) {
        $createdCount++
    }
    elseif ($registerResp.StatusCode -eq 409) {
        $existingLogin = Invoke-JsonPost -Url "$baseUrl/api/auth/login-local" -Payload @{
            email    = $email
            password = $TestUserPassword
        }
        if ($existingLogin.StatusCode -ne 200) {
            throw "User $email already exists but cannot login with provided test password. Response: $($existingLogin.Raw)"
        }
        $existingCount++
    }
    else {
        throw "Failed to register user $email (HTTP $($registerResp.StatusCode)). Response: $($registerResp.Raw)"
    }

    $rows += [pscustomobject]@{
        login_email    = $email
        login_password = $TestUserPassword
    }
}

$outputDir = Split-Path -Parent $OutputCsv
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$rows | Export-Csv -Path $OutputCsv -NoTypeInformation -Encoding UTF8

Write-Host "Account provisioning complete."
Write-Host "Admin verified: $AdminEmail"
Write-Host "Students created: $createdCount"
Write-Host "Students reused: $existingCount"
Write-Host "Users CSV written: $OutputCsv"

exit 0
