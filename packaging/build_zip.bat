@echo off
setlocal
cd /d "%~dp0\.."

if not exist "dist\HDL-Sim\HDL-Sim.exe" (
  echo dist\HDL-Sim\HDL-Sim.exe is missing. Run packaging\build_windows.bat first.
  pause
  exit /b 1
)

for /f "usebackq delims=" %%V in (`py -3.12 -c "import sys; sys.path.insert(0,'src'); from hdl_sim import __version__; print(__version__)"`) do set "VER=%%V"
set "ZIP=dist\HDL-Sim-%VER%-windows-x64.zip"

mkdir "dist\HDL-Sim\verilog_sources" 2>nul
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

echo [HDL-Sim] Creating ZIP: %ZIP%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Compress-Archive -LiteralPath 'dist\HDL-Sim' -DestinationPath '%ZIP%' -Force"
if errorlevel 1 (
  echo ZIP creation failed.
  pause
  exit /b 1
)

echo.
echo Done: %ZIP%
echo Unzip and run HDL-Sim.exe inside the folder.
echo Version: startup window, IDE badge, or Help - About
pause
