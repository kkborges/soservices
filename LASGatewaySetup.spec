# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['installer\\windows\\las_setup_bootstrap.py'],
    pathex=[],
    binaries=[],
    datas=[('installer/windows/bin/nssm.exe', '.')],
    hiddenimports=[
        # Ensure embedded payload execution doesn't fail due to missing runtime libs.
        "urllib.request",
        "tkinter",
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
    name='LASGatewaySetup',
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
)
