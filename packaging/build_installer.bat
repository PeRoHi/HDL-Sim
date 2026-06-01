@echo off
setlocal
cd /d "%~dp0\.."

echo [HDL-Sim] Windows インストーラーをビルドします...
echo.

if not exist "dist\HDL-Sim.exe" (
  echo dist\HDL-Sim.exe がありません。先に packaging\build_windows.bat を実行してください.
  pause
  exit /b 1
)

set "ISCC="
for %%I in (
  "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
  "%ProgramFiles%\Inno Setup 6\ISCC.exe"
) do (
  if exist %%~I set "ISCC=%%~I"
)

if not defined ISCC (
  echo Inno Setup 6 が見つかりません.
  echo https://jrsoftware.org/isdl.php からインストールしてください.
  pause
  exit /b 1
)

"%ISCC%" packaging\hdl_sim_setup.iss
if errorlevel 1 (
  echo インストーラーのビルドに失敗しました.
  pause
  exit /b 1
)

echo.
echo 完成: dist\HDL-Sim-Setup-0.5.0.exe
echo インストール時にショートカット作成や保存フォルダを選択できます.
echo アンインストールは Windows の「アプリと機能」から実行できます.
pause
