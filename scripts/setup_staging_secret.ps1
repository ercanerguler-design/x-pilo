param(
    [Parameter(Mandatory = $true)]
    [string]$Repo,
    [Parameter(Mandatory = $true)]
    [string]$DeployHook,
    [string]$Token = $env:GITHUB_PAT
)

if (-not $Token) {
    Write-Error "GITHUB_PAT yok. Token parametresi ver veya ortam degiskenine ekle."
    exit 1
}

if ($Repo -notmatch "^[^/]+/[^/]+$") {
    Write-Error "Repo owner/name formatinda olmali."
    exit 1
}

$owner, $name = $Repo.Split("/")

$repoInfo = Invoke-RestMethod -Method Get -Uri "https://api.github.com/repos/$owner/$name" -Headers @{ Authorization = "Bearer $Token"; Accept = "application/vnd.github+json" }
$keyInfo = Invoke-RestMethod -Method Get -Uri "https://api.github.com/repos/$owner/$name/actions/secrets/public-key" -Headers @{ Authorization = "Bearer $Token"; Accept = "application/vnd.github+json" }

Add-Type -AssemblyName System.Security
$bytes = [System.Text.Encoding]::UTF8.GetBytes($DeployHook)
$publicKeyBytes = [Convert]::FromBase64String($keyInfo.key)

# GitHub uses libsodium sealed box. If libsodium tooling is unavailable locally, use gh CLI.
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "gh CLI bulunamadi. Lutfen GitHub CLI kur ve su komutu calistir: gh secret set STAGING_DEPLOY_HOOK --repo $Repo --body `"$DeployHook`""
    exit 1
}

$null = gh secret set STAGING_DEPLOY_HOOK --repo $Repo --body "$DeployHook"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Secret set islemi basarisiz."
    exit 1
}

Write-Output "STAGING_DEPLOY_HOOK secret basariyla set edildi: $Repo"
