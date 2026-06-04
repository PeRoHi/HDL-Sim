@echo off
setlocal
cd /d "%~dp0"

set "OUT=redist\MicrosoftEdgeWebview2Setup.exe"
set "URL=https://go.microsoft.com/fwlink/p/?LinkId=2124703"

if exist "%OUT%" (
  echo [HDL-Sim] WebView2 bootstrapper は既にあります: %OUT%
  exit /b 0
)

echo [HDL-Sim] WebView2 bootstrapper をダウンロードしています...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Invoke-WebRequest -Uri '%URL%' -OutFile '%OUT%' -UseBasicParsing"
if errorlevel 1 (
  echo ダウンロードに失敗しました. ブラウザで次を開いて %OUT% に保存してください:
  echo   %URL%
  exit /b 1
)

echo 完成: %OUT%
exit /b 0
