@echo off
setlocal
cd /d "%~dp0\.."

set "PYTHON_VER=3.12.3"
set "PYTHON_ZIP=python-%PYTHON_VER%-embed-amd64.zip"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VER%/%PYTHON_ZIP%"

:: バージョン取得
for /f "usebackq delims=" %%V in (`py -3.12 -c "import sys; sys.path.insert(0,'src'); from hdl_sim import __version__; print(__version__)"`) do set "VER=%%V"
if "%VER%"=="" set "VER=1.0.5"

set "DIST_DIR=dist\HDL-Sim-Portable"
set "ZIP_OUT=dist\HDL-Sim-%VER%-portable-x64.zip"

echo [HDL-Sim] ポータブル版 (BAT起動) のビルドを開始します...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
mkdir "%DIST_DIR%"
mkdir "%DIST_DIR%\python"

:: 1. Download Embedded Python
echo [1/5] Python %PYTHON_VER% Embeddable をダウンロードしています...
if not exist "dist\%PYTHON_ZIP%" (
    powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile 'dist\%PYTHON_ZIP%'"
)
powershell -Command "Expand-Archive -Path 'dist\%PYTHON_ZIP%' -DestinationPath '%DIST_DIR%\python' -Force"

:: 2. Setup pip
echo [2/5] pip をセットアップしています...
powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%DIST_DIR%\python\get-pip.py'"

:: _pthファイルの修正 (import site を有効化して pip を使えるようにする)
powershell -Command "(Get-Content '%DIST_DIR%\python\python312._pth') -replace '#import site', 'import site' | Set-Content '%DIST_DIR%\python\python312._pth'"

:: pipのインストール
"%DIST_DIR%\python\python.exe" "%DIST_DIR%\python\get-pip.py" --no-warn-script-location

:: 3. Install dependencies
echo [3/5] 依存ライブラリをインストールしています...
"%DIST_DIR%\python\python.exe" -m pip install --no-warn-script-location pywebview fastapi uvicorn lark pydantic
"%DIST_DIR%\python\python.exe" -m pip install --no-warn-script-location typing_extensions

:: 4. Copy sources
echo [4/5] ソースコードとアセットをコピーしています...
mkdir "%DIST_DIR%\src"
mkdir "%DIST_DIR%\ui"
mkdir "%DIST_DIR%\examples"
mkdir "%DIST_DIR%\spj"
xcopy /s /e /y src "%DIST_DIR%\src\" >nul
xcopy /s /e /y ui "%DIST_DIR%\ui\" >nul
xcopy /s /e /y examples "%DIST_DIR%\examples\" >nul
xcopy /s /e /y spj "%DIST_DIR%\spj\" >nul

:: pyproject.toml などの必要なメタデータ
copy /y README.md "%DIST_DIR%\" >nul

:: 5. Create launcher BAT
echo [5/5] 起動用バッチファイルを作成しています...
(
echo @echo off
echo cd /d "%%~dp0"
echo set PYTHONPATH=%%~dp0src
echo echo HDL-Sim を起動しています...
echo python\python.exe -m hdl_sim.web.launcher
) > "%DIST_DIR%\HDL-Simを起動.bat"

(
echo @echo off
echo cd /d "%%~dp0"
echo set PYTHONPATH=%%~dp0src
echo echo HDL-Sim を起動しています...
echo python\python.exe -m hdl_sim.web.launcher
) > "%DIST_DIR%\ui.bat"

:: 6. Zip it
echo ZIP アーカイブを作成しています: %ZIP_OUT%
if exist "%ZIP_OUT%" del /f /q "%ZIP_OUT%"
del /q "%DIST_DIR%\spj\*test*.spj" 2>nul
powershell -Command "Compress-Archive -LiteralPath '%DIST_DIR%' -DestinationPath '%ZIP_OUT%' -Force"

:: 7. Create test_spj archive
echo testの .spj アーカイブを作成しています: dist\test_spj.zip
set "TEST_SPJ_DIR=dist\test_spj"
if exist "%TEST_SPJ_DIR%" rmdir /s /q "%TEST_SPJ_DIR%"
mkdir "%TEST_SPJ_DIR%"
copy "spj\*test*.spj" "%TEST_SPJ_DIR%\" >nul 2>&1
if exist "dist\test_spj.zip" del /f /q "dist\test_spj.zip"
powershell -Command "Compress-Archive -LiteralPath '%TEST_SPJ_DIR%' -DestinationPath 'dist\test_spj.zip' -Force"

echo.
echo 完成: %ZIP_OUT%
echo ZIPを解凍し、「HDL-Simを起動.bat」または「ui.bat」をダブルクリックして起動できます。
pause
