# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for PHYS 2150 Measurement Suite

Build command:
    uv run pyinstaller build/phys2150.spec

Or without UV:
    pyinstaller build/phys2150.spec

Output: dist/PHYS2150/ folder with PHYS2150.exe and all dependencies

Note: External hardware drivers (NI-VISA, PicoSDK, Thorlabs OPM)
must be installed separately on the target Windows machine.
"""

import sys
from pathlib import Path

# Get the project root directory (parent of build/)
SPEC_DIR = Path(SPECPATH)
PROJECT_ROOT = SPEC_DIR.parent

block_cipher = None

# Main application entry point
a = Analysis(
    [str(PROJECT_ROOT / 'launcher.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # Include any data files needed
        # (str(PROJECT_ROOT / 'data'), 'data'),
    ],
    hiddenimports=[
        # PySide6 modules
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',

        # Scientific computing
        'numpy',
        'scipy',
        'scipy.signal',
        'pandas',
        'matplotlib',
        'matplotlib.backends.backend_qtagg',

        # Instrument communication
        'pyvisa',
        'pyvisa.resources',

        # PicoScope SDK
        'picosdk',
        'picosdk.ps5000a',
        'picosdk.ps2000a',
        'picosdk.functions',

        # Application modules
        'eqe',
        'eqe.main',
        'eqe.models',
        'eqe.views',
        'eqe.controllers',
        'eqe.drivers',
        'eqe.config',
        'eqe.utils',
        'jv',
        'jv.main',
        'jv.models',
        'jv.views',
        'jv.controllers',
        'jv.config',
        'jv.utils',
        'common',
        'common.drivers',
        'common.ui',
        'common.utils',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'PyQt5',
        'PyQt6',
        'wx',
        'test',
        'unittest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PHYS2150',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Set to True for debugging, False for release
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if available: str(PROJECT_ROOT / 'assets' / 'icon.ico')
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PHYS2150',
)
