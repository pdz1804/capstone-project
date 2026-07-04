param(
    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [string]$RoleName = "GitHubActionsRole",

    [string]$Thumbprint = "6938fd4d98bab03faadb97b34396831e3780aea1",

    [switch]$AttachAdministratorAccess
)

# Don't use $ErrorActionPreference = "Stop" - it causes AWS CLI stderr to throw unexpected exceptions
# Instead, we check $LASTEXITCODE after each AWS CLI call

try {
    $Identity = aws sts get-caller-identity --output json | ConvertFrom-Json
    $AccountId = [string]$Identity.Account
    if ($AccountId -notmatch '^\d{12}$') {
        throw "Invalid account ID: $AccountId"
    }
    Write-Host "AWS Account: $AccountId"
} catch {
    throw "Failed to get AWS account ID: $_"
}

$OidcArn = $null
try {
    $Providers = aws iam list-open-id-connect-providers --output json | ConvertFrom-Json
    if ($Providers.OpenIDConnectProviderList -and $Providers.OpenIDConnectProviderList.Count -gt 0) {
        foreach ($ProviderRef in $Providers.OpenIDConnectProviderList) {
            try {
                $CandidateArn = [string]$ProviderRef.Arn
                if ($CandidateArn -match "token.actions.githubusercontent.com") {
                    $OidcArn = $CandidateArn
                    Write-Host "Found existing OIDC provider: $OidcArn"
                    break
                }
            } catch {
                # Skip this provider, try next
            }
        }
    }
} catch {
    Write-Host "Note: Initial OIDC provider query failed, will attempt creation"
}

if (-not $OidcArn) {
    try {
        Write-Host "Creating new OIDC provider..."
        $CreatedProvider = aws iam create-open-id-connect-provider `
            --url https://token.actions.githubusercontent.com `
            --client-id-list sts.amazonaws.com `
            --thumbprint-list $Thumbprint `
            --output json | ConvertFrom-Json
        $OidcArn = [string]$CreatedProvider.OpenIDConnectProviderArn
        Write-Host "Created OIDC provider: $OidcArn"
    } catch {
        # If creation failed (likely exists), try to fetch the existing one
        if ($_ -match "EntityAlreadyExists") {
            Write-Host "Provider already exists, fetching it..."
            try {
                $Providers = aws iam list-open-id-connect-providers --output json | ConvertFrom-Json
                foreach ($ProviderRef in $Providers.OpenIDConnectProviderList) {
                    $CandidateArn = [string]$ProviderRef.Arn
                    if ($CandidateArn -match "token.actions.githubusercontent.com") {
                        $OidcArn = $CandidateArn
                        Write-Host "Retrieved existing OIDC provider: $OidcArn"
                        break
                    }
                }
            } catch {
                throw "Could not retrieve existing OIDC provider: $_"
            }
        } else {
            throw "Failed to create OIDC provider: $_"
        }
    }
}

if (-not $OidcArn -or $OidcArn -eq "" -or $OidcArn -notmatch "arn:aws:iam") {
    throw "Invalid OIDC provider ARN: '$OidcArn'"
}

# Write trust policy to temp file
$TrustPolicyPath = Join-Path $PSScriptRoot "trust-policy.json"
$TrustPolicy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "$OidcArn"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringLike": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": [
            "repo:${Repo}:ref:refs/heads/main",
            "repo:${Repo}:ref:refs/heads/develop",
            "repo:${Repo}:pull_request"
          ]
        }
      }
    }
  ]
}
"@

# Write UTF-8 WITHOUT BOM - PS 5.1's -Encoding utf8 adds BOM which breaks AWS CLI JSON parsing
[System.IO.File]::WriteAllText($TrustPolicyPath, $TrustPolicy, (New-Object System.Text.UTF8Encoding $false))

# Create or update role - use $LASTEXITCODE since AWS CLI doesn't throw PS exceptions
$RoleCheck = aws iam get-role --role-name $RoleName --output json 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Role does not exist, creating..."
    $CreateResult = aws iam create-role --role-name $RoleName --assume-role-policy-document "file://$TrustPolicyPath" --output json 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create role: $CreateResult"
    }
    Write-Host "Created role: $RoleName"
} else {
    Write-Host "Role exists, updating trust policy..."
    $UpdateResult = aws iam update-assume-role-policy --role-name $RoleName --policy-document "file://$TrustPolicyPath" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to update trust policy: $UpdateResult"
    }
    Write-Host "Updated trust policy for: $RoleName"
}

if ($AttachAdministratorAccess.IsPresent) {
    $AttachResult = aws iam attach-role-policy --role-name $RoleName --policy-arn arn:aws:iam::aws:policy/AdministratorAccess 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Warning: Failed to attach AdministratorAccess: $AttachResult"
    } else {
        Write-Host "Attached AdministratorAccess policy"
    }
}

# Validate role exists and get ARN
$ValidateResult = aws iam get-role --role-name $RoleName --output json 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Failed to validate role: $ValidateResult"
}
$ValidateRole = $ValidateResult | ConvertFrom-Json
$RoleArn = [string]$ValidateRole.Role.Arn

if (-not $RoleArn -or $RoleArn -notmatch "arn:aws:iam::\d{12}:role") {
    throw "Invalid role ARN: $RoleArn"
}
Write-Host ""
Write-Host "=========================================="
Write-Host "OIDC Setup Complete"
Write-Host "=========================================="
Write-Host "OIDC Provider ARN: $OidcArn"
Write-Host "Role ARN: $RoleArn"
Write-Host ""
Write-Host "Set this GitHub secret:"
Write-Host "  AWS_ROLE_TO_ASSUME=$RoleArn"
Write-Host "=========================================="
