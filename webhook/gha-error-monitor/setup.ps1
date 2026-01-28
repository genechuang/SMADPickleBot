# GHA Error Monitor Setup Script
# Run this script to configure all required secrets and variables

$ErrorActionPreference = "Stop"
$PROJECT_ID = "smad-pickleball"

Write-Host "`n=== GHA Error Monitor Setup ===" -ForegroundColor Cyan
Write-Host "This script will configure the secrets and variables needed for the GHA Error Monitor."
Write-Host ""

# 1. Generate webhook secret
$WEBHOOK_SECRET = -join ((48..57) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
Write-Host "[1/5] Generated webhook secret: $WEBHOOK_SECRET" -ForegroundColor Green
Write-Host "      (Save this - you'll need it for GitHub webhook config)"

# 2. Create secrets in GCP Secret Manager
Write-Host "`n[2/5] Creating secrets in GCP Secret Manager..." -ForegroundColor Yellow

# Check if secrets exist, create if not
$secrets = @("ANTHROPIC_API_KEY", "GITHUB_TOKEN", "GITHUB_WEBHOOK_SECRET")
foreach ($secret in $secrets) {
    $exists = gcloud secrets describe $secret --project=$PROJECT_ID 2>$null
    if (-not $exists) {
        Write-Host "      Creating secret: $secret"
        gcloud secrets create $secret --project=$PROJECT_ID --replication-policy="automatic"
    } else {
        Write-Host "      Secret exists: $secret"
    }
}

# 3. Prompt for Anthropic API key
Write-Host "`n[3/5] Setting up Anthropic API Key..." -ForegroundColor Yellow
Write-Host "      Get your API key from: https://console.anthropic.com/settings/keys"
$anthropicKey = Read-Host "      Enter your Anthropic API key (sk-ant-...)"
if ($anthropicKey) {
    $anthropicKey | gcloud secrets versions add ANTHROPIC_API_KEY --project=$PROJECT_ID --data-file=-
    Write-Host "      [OK] Anthropic API key saved" -ForegroundColor Green
}

# 4. Set up GitHub Token
Write-Host "`n[4/5] Setting up GitHub Token..." -ForegroundColor Yellow
Write-Host "      You need a GitHub Personal Access Token with 'repo' scope."
Write-Host "      Create one at: https://github.com/settings/tokens/new"
Write-Host "      Select scope: repo (Full control of private repositories)"
$githubToken = Read-Host "      Enter your GitHub PAT (ghp_...)"
if ($githubToken) {
    $githubToken | gcloud secrets versions add GITHUB_TOKEN --project=$PROJECT_ID --data-file=-
    Write-Host "      [OK] GitHub token saved" -ForegroundColor Green
}

# 5. Set webhook secret
Write-Host "`n[5/5] Setting up GitHub Webhook Secret..." -ForegroundColor Yellow
$WEBHOOK_SECRET | gcloud secrets versions add GITHUB_WEBHOOK_SECRET --project=$PROJECT_ID --data-file=-
Write-Host "      [OK] Webhook secret saved" -ForegroundColor Green

# 6. GitHub repository variable
Write-Host "`n[6/6] Setting up GitHub Repository Variable..." -ForegroundColor Yellow
Write-Host "      Enter your WhatsApp phone number (digits only, with country code)"
Write-Host "      Example: 16265551234 (US number)"
$phoneNumber = Read-Host "      Enter your phone number"
$adminPhoneId = "${phoneNumber}@c.us"
Write-Host "      Setting ADMIN_PHONE_ID=$adminPhoneId"

# Try to set the variable via gh CLI
$ghInstalled = Get-Command gh -ErrorAction SilentlyContinue
if ($ghInstalled) {
    gh variable set ADMIN_PHONE_ID --body $adminPhoneId
    Write-Host "      [OK] GitHub variable set" -ForegroundColor Green
} else {
    Write-Host "      [WARN] gh CLI not installed. Set this manually:" -ForegroundColor Yellow
    Write-Host "      Go to: https://github.com/genechuang/SMADPickleBot/settings/variables/actions"
    Write-Host "      Add variable: ADMIN_PHONE_ID = $adminPhoneId"
}

# Summary
Write-Host "`n=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Push changes to deploy the Cloud Function"
Write-Host "2. After deployment, configure GitHub webhook:"
Write-Host "   - Go to: https://github.com/genechuang/SMADPickleBot/settings/hooks/new"
Write-Host "   - Payload URL: (will be shown after deployment)"
Write-Host "   - Content type: application/json"
Write-Host "   - Secret: $WEBHOOK_SECRET"
Write-Host "   - Events: Select 'Workflow runs'"
Write-Host ""
Write-Host "Webhook secret (copy this for GitHub webhook config):"
Write-Host $WEBHOOK_SECRET -ForegroundColor Magenta
