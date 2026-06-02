@echo off
setlocal
cd /d "%~dp0\.."
rem フリー配布は ZIP を主とする（build_zip.bat）。インストーラーは当面停止。

echo [HDL-Sim] Windows インストーラーをビルドします...
echo.

call packaging\download_webview2.bat
if errorlevel 1 (
  pause
  exit /b 1
)

if not exist "dist\HDL-Sim\HDL-Sim.exe" (
  echo dist\HDL-Sim\HDL-Sim.exe がありません。先に packaging\build_windows.bat を実行してください.
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

set "ISCC_ARGS="
if defined HDL_SIM_SIGN_PFX set "ISCC_ARGS=/DSignedRelease=1"
if defined HDL_SIM_SIGN_THUMBPRINT set "ISCC_ARGS=/DSignedRelease=1"

if defined ISCC_ARGS (
  echo [HDL-Sim] 署名付きインストーラーをビルドします（SIGNING.md 参照）
) else (
  echo [HDL-Sim] 未署名ビルド（SAC で unins000.exe がブロックされる場合あり）
)

"%ISCC%" %ISCC_ARGS% packaging\hdl_sim_setup.iss
if errorlevel 1 (
  echo インストーラーのビルドに失敗しました.
  pause
  exit /b 1
)

echo.
echo 完成: dist\HDL-Sim-Setup-0.5.5.exe
echo WebView2 未導入 PC では Setup 中にランタイムもインストールします.
echo インストール時にショートカット作成や保存フォルダを選択できます.
echo アンインストールは Windows の「アプリと機能」から実行できます.
pause
