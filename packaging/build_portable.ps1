$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot\..

$PYTHON_VER = "3.12.3"
$PYTHON_ZIP = "python-$PYTHON_VER-embed-amd64.zip"
$PYTHON_URL = "https://www.python.org/ftp/python/$PYTHON_VER/$PYTHON_ZIP"

# バージョン取得
$VER = "1.0.1"
try {
    $VER = py -3.12 -c "import sys; sys.path.insert(0,'src'); from hdl_sim import __version__; print(__version__)"
} catch {}

$DIST_DIR = "dist\HDL-Sim-Portable-v106"
$ZIP_OUT = "dist\HDL-Sim-$VER-portable-x64.zip"

Write-Host "[HDL-Sim] Starting robust portable build..." -ForegroundColor Cyan

if (Test-Path $DIST_DIR) {
    Remove-Item -Recurse -Force $DIST_DIR
}
New-Item -ItemType Directory -Path "$DIST_DIR\python" | Out-Null

# 1. Download Embedded Python
Write-Host "[1/6] Downloading Python $PYTHON_VER Embeddable..."
if (-not (Test-Path "dist\$PYTHON_ZIP")) {
    Invoke-WebRequest -Uri $PYTHON_URL -OutFile "dist\$PYTHON_ZIP"
}
Expand-Archive -Path "dist\$PYTHON_ZIP" -DestinationPath "$DIST_DIR\python" -Force

# 2. Setup pip & System DLLs
Write-Host "[2/6] Setting up pip and copying system DLLs..."
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile "$DIST_DIR\python\get-pip.py"

# Enable import site and add ../src to PYTHONPATH
$pth_file = "$DIST_DIR\python\python312._pth"
(Get-Content $pth_file) -replace '#import site', 'import site' | Set-Content $pth_file
Add-Content $pth_file "..\src"

# Install pip
& "$DIST_DIR\python\python.exe" "$DIST_DIR\python\get-pip.py" --no-warn-script-location

# Copy VC++ runtime DLLs from System32 (Ignore errors if missing)
$sys32 = "$env:windir\System32"
Copy-Item -Path "$sys32\vcruntime140.dll" -Destination "$DIST_DIR\python\" -ErrorAction SilentlyContinue
Copy-Item -Path "$sys32\vcruntime140_1.dll" -Destination "$DIST_DIR\python\" -ErrorAction SilentlyContinue
Copy-Item -Path "$sys32\msvcp140.dll" -Destination "$DIST_DIR\python\" -ErrorAction SilentlyContinue

# 3. Install dependencies
Write-Host "[3/6] Installing dependencies..."
& "$DIST_DIR\python\python.exe" -m pip install --no-warn-script-location pywebview fastapi uvicorn lark pydantic
& "$DIST_DIR\python\python.exe" -m pip install --no-warn-script-location typing_extensions

# 4. Copy sources
Write-Host "[4/6] Copying sources and assets..." -ForegroundColor Yellow
Copy-Item -Path "src" -Destination "$DIST_DIR\src" -Recurse -Force
Copy-Item -Path "ui" -Destination "$DIST_DIR\ui" -Recurse -Force

New-Item -ItemType Directory -Force -Path "$DIST_DIR\projects" | Out-Null
New-Item -ItemType Directory -Force -Path "$DIST_DIR\verilog_sources" | Out-Null

New-Item -ItemType Directory -Force -Path "$DIST_DIR\examples" | Out-Null
$exampleFiles = @("and_gate.v", "counter.v", "tb_multi.v", "hierarchy.v")
foreach ($file in $exampleFiles) {
    if (Test-Path "examples\$file") {
        Copy-Item -Path "examples\$file" -Destination "$DIST_DIR\examples\" -Force
    }
}

if (Test-Path "spj") {
    New-Item -ItemType Directory -Force -Path "$DIST_DIR\spj" | Out-Null
    $spjFiles = @("README.md", "api_demo.spj", "silos_code_coverage.spj", "silos_code_coverage2.spj", "silos_gate.spj", "silos_vending.spj", "test4add.spj", "testcounter.spj", "testDFF.spj")
    foreach ($file in $spjFiles) {
        if (Test-Path "spj\$file") {
            Copy-Item -Path "spj\$file" -Destination "$DIST_DIR\spj\" -Force
        }
    }
}
Copy-Item -Path "README.md" -Destination "$DIST_DIR\"

# 5. Download WebView2 Installer
Write-Host "[5/6] Downloading WebView2 Installer..."
Invoke-WebRequest -Uri "https://go.microsoft.com/fwlink/p/?LinkId=2124703" -OutFile "$DIST_DIR\MicrosoftEdgeWebview2Setup.exe"

# 6. Create launcher BAT, VBS, and Debug BAT
Write-Host "[6/6] Creating launcher scripts (Hidden console & Error check)..."
$batContent = @"
@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
powershell -NoProfile -WindowStyle Hidden -Command "Get-ChildItem -Path '.\python' -Recurse -Filter *.dll | Unblock-File" >nul 2>&1
start "" "python\pythonw.exe" -m hdl_sim.web.launcher
"@

$debugBatContent = @"
@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
echo ==============================================
echo HDL-Sim 起動テスト (デバッグモード)
echo ==============================================
echo.
echo セキュリティブロックの解除を行っています...
powershell -NoProfile -Command "Get-ChildItem -Path '.\python' -Recurse -Filter *.dll | Unblock-File"
echo.
echo python.exe を使用して起動し、エラーを画面に表示します...
python\python.exe -m hdl_sim.web.launcher
echo.
echo 処理が終了しました。上記のエラーメッセージを確認してください。
pause
"@

$vbsContent = @"
Set ws = CreateObject("WScript.Shell")
currentDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
ws.CurrentDirectory = currentDir
ws.Environment("Process").Item("PYTHONPATH") = currentDir & "\src"
' Unblock DLLs silently
ws.Run "powershell -NoProfile -WindowStyle Hidden -Command ""Get-ChildItem -Path '.\python' -Recurse -Filter *.dll | Unblock-File""", 0, True
' Run hidden and wait for exit to check error code
exitCode = ws.Run("python\pythonw.exe -m hdl_sim.web.launcher", 0, True)

If exitCode <> 0 Then
    ans = MsgBox("HDL-Sim encountered an error and closed." & vbCrLf & vbCrLf & "If the screen didn't appear, you might be missing the WebView2 Runtime." & vbCrLf & "Would you like to run the included WebView2 Installer?", 4 + 16, "Startup Error")
    If ans = 6 Then ' vbYes
        ws.Run "MicrosoftEdgeWebview2Setup.exe", 1, False
    End If
End If
"@

Set-Content -Path "$DIST_DIR\start_hdl_sim.bat" -Value $batContent -Encoding Ascii
Set-Content -Path "$DIST_DIR\ui.bat" -Value $batContent -Encoding Ascii
Set-Content -Path "$DIST_DIR\デバッグ起動.bat" -Value $debugBatContent -Encoding Default
Set-Content -Path "$DIST_DIR\ui.vbs" -Value $vbsContent -Encoding Ascii
Set-Content -Path "$DIST_DIR\HDL-Simを起動.vbs" -Value $vbsContent -Encoding Default

# 7. Zip it
Write-Host "Creating ZIP archive: $ZIP_OUT"
if (Test-Path $ZIP_OUT) {
    Remove-Item -Force $ZIP_OUT
}
Compress-Archive -LiteralPath $DIST_DIR -DestinationPath $ZIP_OUT -Force

Write-Host "Creating test SPJ archive: dist\test_spj.zip"
$TEST_SPJ_DIR = "dist\test_spj"
if (Test-Path $TEST_SPJ_DIR) { Remove-Item -Recurse -Force $TEST_SPJ_DIR }
New-Item -ItemType Directory -Force -Path $TEST_SPJ_DIR | Out-Null
Get-ChildItem -Path "spj" -Filter "*test*.spj" | Copy-Item -Destination $TEST_SPJ_DIR -Force
if (Test-Path "dist\test_spj.zip") { Remove-Item -Force "dist\test_spj.zip" }
Compress-Archive -LiteralPath $TEST_SPJ_DIR -DestinationPath "dist\test_spj.zip" -Force

Write-Host ""
Write-Host "Done: $ZIP_OUT" -ForegroundColor Green
Write-Host "Please extract the ZIP and run ui.vbs"
