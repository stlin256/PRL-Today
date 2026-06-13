# -*- mode: python ; coding: utf-8 -*-

import sys

WINDOWS = sys.platform == 'win32'
MACOS = sys.platform == 'darwin'
ICON_PATH = 'assets/app_icon.ico' if WINDOWS else None

a = Analysis(
    ['run.py'],
    pathex=['src'],
    binaries=[],
    datas=[
        ('config.example.json', '.'),
        ('assets/prl_logo.png', 'assets'),
        ('assets/github_mark.png', 'assets'),
        ('assets/app_icon.png', 'assets'),
        ('assets/app_icon.ico', 'assets'),
    ],
    hiddenimports=['prl_profit_float.qt_app', 'PyQt5.QtWidgets'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt6',
        'PyQt5.QtDBus',
        'PyQt5.QtDesigner',
        'PyQt5.QtHelp',
        'PyQt5.QtMultimedia',
        'PyQt5.QtNetwork',
        'PyQt5.QtOpenGL',
        'PyQt5.QtPdf',
        'PyQt5.QtPrintSupport',
        'PyQt5.QtQml',
        'PyQt5.QtQuick',
        'PyQt5.QtSql',
        'PyQt5.QtSvg',
        'PyQt5.QtTest',
        'PyQt5.QtWebChannel',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebSockets',
        'PyQt5.QtXml',
    ],
    noarchive=False,
    optimize=0,
)

excluded_qt_names = (
    'Qt5DBus',
    'Qt5Network',
    'Qt5Pdf',
    'Qt5Qml',
    'Qt5QmlModels',
    'Qt5Quick',
    'Qt5Svg',
    'Qt5VirtualKeyboard',
    'Qt5WebSockets',
)
excluded_plugin_parts = (
    'PyQt5\\Qt5\\plugins\\generic\\',
    'PyQt5\\Qt5\\plugins\\iconengines\\',
    'PyQt5\\Qt5\\plugins\\imageformats\\qgif',
    'PyQt5\\Qt5\\plugins\\imageformats\\qicns',
    'PyQt5\\Qt5\\plugins\\imageformats\\qico',
    'PyQt5\\Qt5\\plugins\\imageformats\\qjpeg',
    'PyQt5\\Qt5\\plugins\\imageformats\\qpdf',
    'PyQt5\\Qt5\\plugins\\imageformats\\qsvg',
    'PyQt5\\Qt5\\plugins\\imageformats\\qtga',
    'PyQt5\\Qt5\\plugins\\imageformats\\qtiff',
    'PyQt5\\Qt5\\plugins\\imageformats\\qwbmp',
    'PyQt5\\Qt5\\plugins\\imageformats\\qwebp',
    'PyQt5\\Qt5\\plugins\\platforminputcontexts\\',
    'PyQt5\\Qt5\\plugins\\platforms\\qdirect2d',
    'PyQt5\\Qt5\\plugins\\platforms\\qminimal',
    'PyQt5\\Qt5\\plugins\\platforms\\qoffscreen',
    'PyQt5\\Qt5\\plugins\\platforms\\qwebgl',
    'PyQt5\\Qt5\\plugins\\platformthemes\\',
    'PyQt5\\Qt5\\plugins\\styles\\',
)

a.binaries = [
    item for item in a.binaries
    if not any(item[0].startswith(name) for name in excluded_qt_names)
    and not any(part in item[0] for part in excluded_plugin_parts)
    and item[0] not in {'opengl32sw.dll', 'libEGL.dll', 'libGLESv2.dll'}
]
a.datas = [
    item for item in a.datas
    if 'PyQt5\\Qt5\\translations\\' not in item[0]
]
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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=ICON_PATH,
    codesign_identity=None,
    entitlements_file=None,
)

if MACOS:
    app = BUNDLE(
        exe,
        name='PRL-Today.app',
        bundle_identifier='com.stlin256.prltoday',
    )
