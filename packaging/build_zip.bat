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

:: ユーザー要望のフォルダとファイルの整理
mkdir "dist\HDL-Sim\verilog_sources" 2>nul

:: ユーザーが見える最上位階層に spj フォルダを作成し、吟味済みのプロジェクトを配置
mkdir "dist\HDL-Sim\spj" 2>nul
copy "spj\api_demo.spj" "dist\HDL-Sim\spj\" >nul 2>&1
copy "spj\silos_code_coverage.spj" "dist\HDL-Sim\spj\" >nul 2>&1
copy "spj\silos_code_coverage2.spj" "dist\HDL-Sim\spj\" >nul 2>&1
copy "spj\silos_gate.spj" "dist\HDL-Sim\spj\" >nul 2>&1
copy "spj\silos_vending.spj" "dist\HDL-Sim\spj\" >nul 2>&1
copy "spj\test4add.spj" "dist\HDL-Sim\spj\" >nul 2>&1
copy "spj\testcounter.spj" "dist\HDL-Sim\spj\" >nul 2>&1
copy "spj\testDFF.spj" "dist\HDL-Sim\spj\" >nul 2>&1

set EX_DIR=dist\HDL-Sim\_internal\examples
if not exist "%EX_DIR%" set EX_DIR=dist\HDL-Sim\examples
rmdir /s /q "%EX_DIR%" 2>nul
mkdir "%EX_DIR%" 2>nul
copy "examples\and_gate.v" "%EX_DIR%\" >nul 2>&1
copy "examples\counter.v" "%EX_DIR%\" >nul 2>&1
copy "examples\tb_multi.v" "%EX_DIR%\" >nul 2>&1
copy "examples\hierarchy.v" "%EX_DIR%\" >nul 2>&1
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
