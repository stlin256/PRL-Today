# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('config.example.json', '.'),
        ('assets/prl_logo.svg', 'assets'),
        ('assets/github_mark.svg', 'assets'),
        ('assets/app_icon.ico', 'assets'),
    ],
    hiddenimports=['prl_profit_float.qt_app', 'PyQt5.QtWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6'],
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
    exclude_binaries=False,
    name='PRL-Today',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon='assets/app_icon.ico',
    codesign_identity=None,
    entitlements_file=None,
)
