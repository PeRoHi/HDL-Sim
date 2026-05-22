@echo off
cd /d %~dp0
where python >nul 2>nul
if %errorlevel%==0 (
  python start_ui.py %*
  goto :eof
)
where py >nul 2>nul
if %errorlevel%==0 (
  py start_ui.py %*
  goto :eof
)
echo Python が見つかりません。Python 3.12 をインストールしてください。
pause
