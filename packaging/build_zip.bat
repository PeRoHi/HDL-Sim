@echo off
setlocal
cd /d "%~dp0\.."

if not exist "dist\HDL-Sim\HDL-Sim.exe" (
  echo dist\HDL-Sim\HDL-Sim.exe がありません。先に packaging\build_windows.bat を実行してください.
  pause
  exit /b 1
)

for /f "usebackq delims=" %%V in (`py -3.12 -c "import sys; sys.path.insert(0,'src'); from hdl_sim import __version__; print(__version__)"`) do set "VER=%%V"
set "ZIP=dist\HDL-Sim-%VER%-windows-x64.zip"

if exist "%ZIP%" del /f /q "%ZIP%"

echo [HDL-Sim] ZIP を作成しています: %ZIP%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -LiteralPath 'dist\HDL-Sim' -DestinationPath '%ZIP%' -Force"
if errorlevel 1 (
  echo ZIP の作成に失敗しました.
  pause
  exit /b 1
)

echo.
echo 完成: %ZIP%
echo ユーザーは ZIP を解凍し、フォルダ内の HDL-Sim.exe を実行します。
echo バージョン確認: 起動ウィンドウの Ver 表示、または IDE 左上 / Help - About
pause
