# -*- mode: python ; coding: utf-8 -*-
# Build on Windows:
#   py -3.12 -m pip install pyinstaller pywebview fastapi uvicorn lark
#   py -3.12 -m PyInstaller packaging/hdl_sim_ui.spec
#
# Installer (after exe build):
#   packaging\build_installer.bat

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).resolve().parent

webview_hidden = collect_submodules("webview")
hdl_sim_hidden = collect_submodules("hdl_sim")
uvicorn_hidden = collect_submodules("uvicorn")
fastapi_hidden = collect_submodules("fastapi")
parser_data = [
    (str(root / "src" / "hdl_sim" / "parser" / "verilog.lark"), "hdl_sim/parser"),
]

a = Analysis(
    [str(root / 'start_ui_gui.pyw')],
    pathex=[str(root / 'src')],
    binaries=[],
    datas=[
        (str(root / 'ui'), 'ui'),
        (str(root / 'examples'), 'examples'),
        (str(root / 'spj'), 'spj'),
        *parser_data,
        *collect_data_files('lark'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'lark',
        'webview',
        'hdl_sim.parser',
        'hdl_sim.web.app',
        'hdl_sim.web.gui_launcher',
        'hdl_sim.web.launcher',
        'hdl_sim.web.native_window',
        'hdl_sim.web.runtime',
        'hdl_sim.web.paths',
        'hdl_sim.web.vcd_json',
        'hdl_sim.web.update_checker',
        'hdl_sim.web.crash_log',
        *webview_hidden,
        *hdl_sim_hidden,
        *uvicorn_hidden,
        *fastapi_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[
        str(root / 'packaging' / 'pyi_rth_cwd.py'),
        str(root / 'packaging' / 'pyi_rth_stdio.py'),
    ],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HDL-Sim',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='HDL-Sim',
)
