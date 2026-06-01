# -*- mode: python ; coding: utf-8 -*-
# Build on Windows:
#   py -3.12 -m pip install pyinstaller pywebview fastapi uvicorn lark
#   py -3.12 -m PyInstaller packaging/hdl_sim_ui.spec

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH).resolve().parent

webview_hidden = collect_submodules("webview")

a = Analysis(
    [str(root / 'start_ui_gui.pyw')],
    pathex=[str(root / 'src')],
    binaries=[],
    datas=[
        (str(root / 'ui'), 'ui'),
        (str(root / 'examples'), 'examples'),
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
        'hdl_sim.web.app',
        'hdl_sim.web.gui_launcher',
        'hdl_sim.web.launcher',
        'hdl_sim.web.native_window',
        'hdl_sim.web.paths',
        'hdl_sim.web.vcd_json',
        *webview_hidden,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HDL-Sim',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
