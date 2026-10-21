# -*- mode: python ; coding: utf-8 -*-
# PyInstaller build specification for DualDesk Standalone Windows Executable

from pathlib import Path

block_cipher = None
project_root = Path(__file__).resolve().parent.parent

a = Analysis(
    [str(project_root / 'src' / 'dualdesk' / '__main__.py')],
    pathex=[str(project_root / 'src')],
    binaries=[],
    datas=[
        (str(project_root / 'scripts' / 'configure_firewall.ps1'), 'scripts'),
        (str(project_root / 'scripts' / 'build_driver.ps1'), 'scripts'),
        (str(project_root / 'native' / 'idd_driver' / 'IddDriver.inf'), 'driver'),
    ],
    hiddenimports=[
        'dualdesk',
        'dualdesk.audio',
        'dualdesk.audio.capture',
        'dualdesk.diagnostics',
        'dualdesk.diagnostics.bundle',
        'dualdesk.display',
        'dualdesk.display.adaptive',
        'dualdesk.display.capture',
        'dualdesk.display.clipboard',
        'dualdesk.display.decoder',
        'dualdesk.display.driver',
        'dualdesk.display.dxgi_capture',
        'dualdesk.display.encoder',
        'dualdesk.display.input_injector',
        'dualdesk.display.multimonitor',
        'dualdesk.network',
        'dualdesk.network.discovery',
        'dualdesk.network.file_transfer',
        'dualdesk.network.transport',
        'dualdesk.platform',
        'dualdesk.platform.autostart',
        'dualdesk.protocol',
        'dualdesk.protocol.models',
        'dualdesk.security',
        'dualdesk.security.clipboard_guard',
        'dualdesk.security.crypto',
        'dualdesk.security.input_filter',
        'dualdesk.security.pairing',
        'dualdesk.security.tls',
        'dualdesk.storage',
        'dualdesk.storage.db',
        'dualdesk.ui',
        'dualdesk.ui.app',
        'dualdesk.ui.components',
        'dualdesk.ui.viewer',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'cryptography',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest'],
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
    name='DualDesk',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='dualdesk',
)
