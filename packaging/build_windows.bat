@echo off
setlocal
cd /d "%~dp0\.."
echo [HDL-Sim] Windows 配布版をビルドします...
py -3.12 -m pip install pyinstaller pywebview fastapi uvicorn lark
if exist "dist\HDL-Sim" rmdir /s /q "dist\HDL-Sim"
if exist "build" rmdir /s /q "build"
py -3.12 -m PyInstaller packaging/hdl_sim_ui.spec --noconfirm
if errorlevel 1 exit /b 1

if defined HDL_SIM_SIGN_PFX goto :sign
if defined HDL_SIM_SIGN_THUMBPRINT goto :sign
goto :nosign
:sign
echo [HDL-Sim] HDL-Sim.exe にコード署名しています...
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\sign_file.ps1 -Path dist\HDL-Sim\HDL-Sim.exe
if errorlevel 1 exit /b 1
goto :done
:nosign
echo [HDL-Sim] コード署名はスキップ（HDL_SIM_SIGN_PFX または HDL_SIM_SIGN_THUMBPRINT 未設定）
:done
echo.
echo 完成: dist\HDL-Sim\HDL-Sim.exe
echo dist\HDL-Sim フォルダ全体が実行に必要です。
echo.
echo ZIP 配布: packaging\build_zip.bat
echo インストーラー: packaging\build_installer.bat （当面は未使用・Inno Setup 6）
pause
