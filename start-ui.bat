@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "PY="
for %%P in ("py -3.12" "py -3" "python" "python3") do (
  call :try_python %%~P
  if defined PY goto :launch
)

echo.
echo [HDL-Sim] Python 3.12 was not found.
echo.
echo 1. Install Python 3.12 from https://www.python.org/downloads/
echo 2. Enable "Add python.exe to PATH"
echo 3. Use the python.org installer, not Microsoft Store
echo.
pause
exit /b 1

:launch
echo [HDL-Sim] Starting...
set "PYTHONPATH=%~dp0src"
"%PY%" "%~dp0start_ui.py" --gui --window %*
set "RC=!errorlevel!"
if not "!RC!"=="0" (
  echo.
  echo [HDL-Sim] Start failed. Exit code !RC!
  echo First-time setup:
  echo   "%PY%" -m pip install fastapi uvicorn lark
  echo.
  pause
)
exit /b !RC!

:try_python
set "CAND=%~1"
%CAND% -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
for /f "delims=" %%V in ('%CAND% -c "import sys; print(sys.executable)"') do set "PY=%%V"
exit /b 0
