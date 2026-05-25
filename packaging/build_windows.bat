@echo off
setlocal
cd /d "%~dp0\.."
echo [HDL-Sim] Windows 配布版をビルドします...
py -3.12 -m pip install pyinstaller fastapi uvicorn lark
py -3.12 -m PyInstaller packaging/hdl_sim_ui.spec --noconfirm
echo.
echo 完成: dist\HDL-Sim.exe
echo この exe を配布すれば Python なし・ターミナルなしで起動できます。
pause
