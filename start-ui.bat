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
echo [HDL-Sim] Python 3.12 が見つかりません。
echo.
echo 1. https://www.python.org/downloads/ から Python 3.12 をインストール
echo 2. インストール時に "Add python.exe to PATH" にチェック
echo 3. Microsoft Store 版ではなく python.org 版を推奨
echo.
pause
exit /b 1

:launch
echo [HDL-Sim] 起動中...
set "PYTHONPATH=%~dp0src"
"%PY%" "%~dp0start_ui.py" --gui --window %*
set "RC=!errorlevel!"
if not "!RC!"=="0" (
  echo.
  echo [HDL-Sim] 起動に失敗しました ^(code=!RC!^).
  echo 初回のみ次を実行してください:
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
