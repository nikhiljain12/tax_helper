# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules


PROJECT_ROOT = Path.cwd().resolve()
MACOS_ICON = PROJECT_ROOT / 'build' / 'macos' / 'TaxPDFRedactor.icns'

hiddenimports = collect_submodules('fitz') + collect_submodules('app')


a = Analysis(
    ['desktop_main.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name='TaxPDFRedactor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TaxPDFRedactor',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='TaxPDFRedactor.app',
        icon=str(MACOS_ICON) if MACOS_ICON.exists() else None,
        bundle_identifier='com.taxhelper.taxpdfredactor',
        info_plist={
            'CFBundleName': 'Tax PDF Redactor',
            'CFBundleDisplayName': 'Tax PDF Redactor',
            'CFBundleShortVersionString': '0.1.0',
            'CFBundleVersion': '0.1.0',
            'NSHighResolutionCapable': True,
        },
    )
