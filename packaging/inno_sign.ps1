# Inno Setup SignTool hook — signs the file Inno passes as the first argument.
param([string]$FilePath = $args[0])

if (-not $FilePath) {
    Write-Error "Inno SignTool: no file path argument."
}

$signScript = Join-Path $PSScriptRoot "sign_file.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $signScript -Path $FilePath
