@echo off
setlocal
cd /d "%~dp0\.."
echo [HDL-Sim] Windows 配布版をビルドします...
py -3.12 -m pip install pyinstaller pywebview fastapi uvicorn lark
if exist "dist\HDL-Sim" rmdir /s /q "dist\HDL-Sim"
if exist "build" rmdir /s /q "build"
py -3.12 -m PyInstaller packaging/hdl_sim_ui.spec --noconfirm
echo.
echo 完成: dist\HDL-Sim\HDL-Sim.exe
echo dist\HDL-Sim フォルダ全体が実行に必要です。
echo.
echo インストーラー版: packaging\build_installer.bat （Inno Setup 6 が必要）
pause
