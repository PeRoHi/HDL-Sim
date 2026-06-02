# Sign a Windows PE file with Authenticode when credentials are configured.
# Usage: powershell -File packaging\sign_file.ps1 -Path "dist\HDL-Sim\HDL-Sim.exe"
param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Error "File not found: $Path"
}

function Find-SignTool {
    $kits = "${env:ProgramFiles(x86)}\Windows Kits\10\bin"
    if (-not (Test-Path $kits)) {
        return $null
    }
    Get-ChildItem -Path $kits -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending |
        ForEach-Object {
            $candidate = Join-Path $_.FullName "x64\signtool.exe"
            if (Test-Path $candidate) { return $candidate }
        }
    return $null
}

$signtool = Find-SignTool
if (-not $signtool) {
    Write-Error "signtool.exe not found. Install Windows SDK (Signing Tools)."
}

$timestamp = $env:HDL_SIM_TIMESTAMP_URL
if (-not $timestamp) {
    $timestamp = "http://timestamp.digicert.com"
}

$args = @("sign", "/fd", "sha256", "/tr", $timestamp, "/td", "sha256", "/v")

$thumb = $env:HDL_SIM_SIGN_THUMBPRINT
$pfx = $env:HDL_SIM_SIGN_PFX
$password = $env:HDL_SIM_SIGN_PASSWORD

if ($thumb) {
    $args += @("/sha1", $thumb)
}
elseif ($pfx) {
    if (-not (Test-Path -LiteralPath $pfx)) {
        Write-Error "HDL_SIM_SIGN_PFX not found: $pfx"
    }
    $args += @("/f", $pfx)
    if ($password) {
        $args += @("/p", $password)
    }
}
else {
    Write-Host "[HDL-Sim] Signing skipped (set HDL_SIM_SIGN_THUMBPRINT or HDL_SIM_SIGN_PFX)."
    exit 0
}

& $signtool @args $Path
if ($LASTEXITCODE -ne 0) {
    Write-Error "signtool failed with exit code $LASTEXITCODE"
}

Write-Host "[HDL-Sim] Signed: $Path"
