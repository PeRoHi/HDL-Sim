@echo off
setlocal
cd /d "%~dp0\.."
echo [HDL-Sim] Building Windows distribution...
py -3.12 -m pip install pyinstaller pywebview fastapi uvicorn lark
if exist "dist\HDL-Sim" rmdir /s /q "dist\HDL-Sim"
if exist "build" rmdir /s /q "build"
py -3.12 -m PyInstaller packaging/hdl_sim_ui.spec --noconfirm
if errorlevel 1 exit /b 1

if defined HDL_SIM_SIGN_PFX goto :sign
if defined HDL_SIM_SIGN_THUMBPRINT goto :sign
goto :nosign
:sign
echo [HDL-Sim] Signing HDL-Sim.exe...
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\sign_file.ps1 -Path dist\HDL-Sim\HDL-Sim.exe
if errorlevel 1 exit /b 1
goto :done
:nosign
echo [HDL-Sim] Code signing skipped. Set HDL_SIM_SIGN_PFX or HDL_SIM_SIGN_THUMBPRINT to sign.
:done
echo.
echo Output: dist\HDL-Sim\HDL-Sim.exe
echo The whole dist\HDL-Sim folder is required at runtime.
echo.
echo ZIP: packaging\build_zip.bat
echo Installer: packaging\build_installer.bat currently unused.
pause
