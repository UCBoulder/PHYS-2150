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
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Get the project root directory (parent of build/)
SPEC_DIR = Path(SPECPATH)
PROJECT_ROOT = SPEC_DIR.parent

block_cipher = None

# Collect all numpy components (required for NumPy 2.x)
numpy_datas, numpy_binaries, numpy_hiddenimports = collect_all('numpy')

# Collect scipy as well
scipy_datas, scipy_binaries, scipy_hiddenimports = collect_all('scipy')

# Collect certifi for SSL certificates (needed for HTTPS requests in frozen app)
certifi_datas, certifi_binaries, certifi_hiddenimports = collect_all('certifi')

# Main application entry point
a = Analysis(
    [str(PROJECT_ROOT / 'launcher.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=numpy_binaries + scipy_binaries,
    datas=[
        # Web UI files (HTML, CSS, JavaScript)
        (str(PROJECT_ROOT / 'ui'), 'ui'),
        # Application icon
        (str(PROJECT_ROOT / 'assets'), 'assets'),
    ] + numpy_datas + scipy_datas + certifi_datas,
    hiddenimports=[
        # PySide6 core modules
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',

        # PySide6 WebEngine modules (for web UI)
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebChannel',

        # pandas (scipy/numpy collected separately above)
        'pandas',

        # Instrument communication
        'pyvisa',
        'pyvisa.resources',

        # PicoScope SDK
        'picosdk',
        'picosdk.ps5000a',
        'picosdk.ps2000',
        'picosdk.ps2000a',
        'picosdk.functions',

        # Application modules - EQE
        'eqe',
        'eqe.web_main',
        'eqe.models',
        'eqe.controllers',
        'eqe.drivers',
        'eqe.config',
        'eqe.utils',

        # Application modules - JV
        'jv',
        'jv.web_main',
        'jv.models',
        'jv.controllers',
        'jv.config',
        'jv.utils',

        # Common modules
        'common',
        'common.drivers',
        'common.ui',
        'common.utils',

        # SSL certificates
        'certifi',
    ] + numpy_hiddenimports + scipy_hiddenimports + certifi_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'PyQt5',
        'PyQt6',
        'wx',
        'matplotlib',  # Replaced by Plotly.js in web UI
        'test',
        # Note: Don't exclude 'unittest' - scipy needs it for array_api_compat
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
    icon=str(PROJECT_ROOT / 'assets' / 'icon.ico') if (PROJECT_ROOT / 'assets' / 'icon.ico').exists() else None,
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
